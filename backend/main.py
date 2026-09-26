"""Main FastAPI application entrypoint for SafeAI Core."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.explainer.engine import ExplainerEngine
from backend.gateway.mcp_server import MCPServerRouter
from backend.gateway.openai_proxy import OpenAIProxyRouter
from backend.gateway.proxy import GatewayProxy
from backend.hitl.broker import HITLBroker
from backend.models.schemas import SystemConfig
from backend.routes.api import create_api_router
from backend.routes.ws import ConnectionManager, create_ws_router
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


def create_app(db_path: Optional[str] = None) -> FastAPI:
    """Factory creating and wiring all SafeAI Core subsystems."""

    # 1. Initialize Storage & Config
    store = AuditStore(db_path=db_path)
    config = SystemConfig()

    # 2. Core Security & Explainer Engines
    dlp = DLPMasker()
    active_rules = store.get_policy_rules(active_only=True)
    sec_engine = SecurityEngine(policy_rules=active_rules)
    explainer = ExplainerEngine()

    # 3. HITL Connection Holding Broker
    hitl_broker = HITLBroker(
        approval_threshold=config.approval_threshold,
        timeout_seconds=config.approval_timeout_seconds,
    )

    # 4. WebSockets Event Manager
    ws_manager = ConnectionManager(hitl_broker=hitl_broker)
    # Wire broker notification callback to broadcast over WebSockets
    hitl_broker.set_ws_notifier(ws_manager.broadcast)

    # 5. Gateway Ingestion Layer (MCP & OpenAI)
    downstream_url = os.environ.get("DOWNSTREAM_MCP_URL")
    gateway_proxy = GatewayProxy(
        security_engine=sec_engine,
        explainer_engine=explainer,
        hitl_broker=hitl_broker,
        dlp_masker=dlp,
        audit_store=store,
        downstream_url=downstream_url,
        default_language=config.active_language,
    )

    mcp_router = MCPServerRouter(gateway_proxy=gateway_proxy)
    openai_router = OpenAIProxyRouter(
        security_engine=sec_engine,
        explainer_engine=explainer,
        hitl_broker=hitl_broker,
        dlp_masker=dlp,
        audit_store=store,
        default_language=config.active_language,
    )

    # 6. Automated Copilot & Antigravity Chat Ingestion Syncers
    from backend.storage.copilot_sync import CopilotChatSyncer
    from backend.storage.antigravity_sync import AntigravityChatSyncer

    copilot_syncer = CopilotChatSyncer(
        audit_store=store,
        dlp_masker=dlp,
        ws_broadcast=ws_manager.broadcast,
    )
    antigravity_syncer = AntigravityChatSyncer(
        audit_store=store,
        dlp_masker=dlp,
        ws_broadcast=ws_manager.broadcast,
    )

    # 7. Lifespan context manager for background watchers
    @asynccontextmanager
    async def lifespan(fastapi_app: FastAPI):
        # Sync immediately on startup
        try:
            copilot_syncer.sync_all(max_files=50)
            antigravity_syncer.sync_all(max_files=50)
        except Exception:
            pass

        async def chat_watch_loop():
            while True:
                try:
                    await asyncio.sleep(3)
                    copilot_syncer.sync_recent(max_files=50)
                    antigravity_syncer.sync_recent(max_files=50)
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass

        watch_task = asyncio.create_task(chat_watch_loop())
        yield
        watch_task.cancel()

    # 8. Build FastAPI App
    app = FastAPI(
        title="SafeAI Core Gateway",
        description="Local-first AI agent security governance proxy and plain-language explainer",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Permissive local CORS for dashboard Web Panel
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Attach Routers
    app.include_router(mcp_router.router)
    app.include_router(openai_router.router)
    app.include_router(create_ws_router(ws_manager, hitl_broker))
    app.include_router(
        create_api_router(
            store,
            hitl_broker,
            sec_engine,
            config,
            copilot_syncer=copilot_syncer,
            explainer_engine=explainer,
        )
    )

    # Health check endpoint
    @app.get("/healthz")
    def health_check():
        return {
            "status": "healthy",
            "gateway": "SafeAI Core",
            "threshold": config.approval_threshold,
            "language": config.active_language,
        }

    # Mount static frontend files if built
    frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dist.exists() and frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8080, reload=True)
