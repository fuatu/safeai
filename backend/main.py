"""Main FastAPI application entrypoint for SafeAI Core."""

import asyncio
import os
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

    # 6. Build FastAPI App
    app = FastAPI(
        title="SafeAI Core Gateway",
        description="Local-first AI agent security governance proxy and plain-language explainer",
        version="1.0.0",
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
            ws_broadcast=ws_manager.broadcast,
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

def run_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = True):
    import socket
    import uvicorn

    try:
        # Bind dual-stack socket (IPv6 + IPv4) so 'localhost' resolves reliably
        # on both macOS and Linux regardless of whether client connects via ::1 or 127.0.0.1
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("::", port))
        sock.listen(256)
        config = uvicorn.Config(app="backend.main:app", reload=reload)
        server = uvicorn.Server(config)
        server.run(sockets=[sock])
    except Exception:
        uvicorn.run("backend.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    run_server()
