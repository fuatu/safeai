"""FastAPI router implementing MCP Streamable HTTP and SSE transports."""

import asyncio
import json
import uuid
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.gateway.proxy import GatewayProxy


class MCPServerRouter:
    """Manages MCP SSE client channels and routes incoming JSON-RPC traffic."""

    def __init__(self, gateway_proxy: GatewayProxy):
        self.gateway_proxy = gateway_proxy
        self.router = APIRouter()
        self._sse_queues: Dict[str, asyncio.Queue] = {}
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.get("/mcp")
        async def mcp_sse_endpoint(
            request: Request,
            client_name: Optional[str] = Query(None, description="Name of connecting client"),
        ):
            """
            Establishes an MCP Server-Sent Events (SSE) stream.
            Sends an initial 'endpoint' event with the messages submission URL.
            """
            # Detect client from query param or User-Agent header
            user_agent = (request.headers.get("user-agent") or "").lower()
            resolved_client = client_name
            if not resolved_client or resolved_client == "AI Client":
                if "copilot" in user_agent or "code" in user_agent:
                    resolved_client = "VS Code + GitHub Copilot"
                elif "claude" in user_agent:
                    resolved_client = "Claude Desktop"
                elif "cursor" in user_agent:
                    resolved_client = "Cursor"
                elif "antigravity" in user_agent:
                    resolved_client = "Google Antigravity"
                else:
                    resolved_client = "VS Code + GitHub Copilot"

            session_id = str(uuid.uuid4())
            queue: asyncio.Queue = asyncio.Queue()
            self._sse_queues[session_id] = queue
            self.gateway_proxy.get_or_create_session(
                session_id,
                client_name=resolved_client,
                title=f"{resolved_client} (Connected)",
            )

            async def event_generator():
                try:
                    # Initial endpoint event per MCP SSE spec
                    endpoint_msg = f"/mcp/messages?sessionId={session_id}"
                    yield f"event: endpoint\ndata: {endpoint_msg}\n\n"

                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                            yield f"event: message\ndata: {json.dumps(msg)}\n\n"
                        except asyncio.TimeoutError:
                            # Ping keep-alive
                            yield ": ping\n\n"
                finally:
                    self._sse_queues.pop(session_id, None)

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        @self.router.post("/mcp/messages")
        async def mcp_post_message(
            request: Request,
            sessionId: str = Query(..., description="Session ID returned by SSE endpoint"),
            lang: Optional[str] = Query(None, description="Active language code"),
        ):
            """Receives client JSON-RPC messages and routes them through GatewayProxy."""
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            response = await self.gateway_proxy.handle_mcp_request(
                request_dict=body,
                session_id=sessionId,
                active_language=lang,
            )

            # If SSE queue exists for this session, push response to SSE stream
            queue = self._sse_queues.get(sessionId)
            if queue:
                await queue.put(response)
                return JSONResponse({"status": "accepted"})

            return JSONResponse(response)

        @self.router.post("/mcp")
        async def mcp_direct_jsonrpc(
            request: Request,
            sessionId: Optional[str] = Query(None),
            client_name: str = Query("AI Client"),
            lang: Optional[str] = Query(None),
        ):
            """Direct Streamable HTTP JSON-RPC endpoint for MCP clients."""
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            response = await self.gateway_proxy.handle_mcp_request(
                request_dict=body,
                session_id=sessionId,
                client_name=client_name,
                active_language=lang,
            )
            return JSONResponse(response)
