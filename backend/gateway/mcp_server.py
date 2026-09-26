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
        self._connection_to_session: Dict[str, str] = {}
        self._connection_to_client: Dict[str, str] = {}
        self._setup_routes()

    def _infer_active_client(self) -> str:
        try:
            import time
            from backend.storage.antigravity_sync import AntigravityChatSyncer
            from backend.storage.copilot_sync import CopilotChatSyncer
            ag_syncer = AntigravityChatSyncer(audit_store=self.gateway_proxy.audit_store)
            cp_syncer = CopilotChatSyncer(audit_store=self.gateway_proxy.audit_store)
            ag_file = ag_syncer.get_latest_transcript_file()
            cp_file = cp_syncer.get_latest_chat_session_file()
            ag_mtime = ag_file.stat().st_mtime if ag_file else 0
            cp_mtime = cp_file.stat().st_mtime if cp_file else 0

            if ag_mtime > cp_mtime and ag_mtime > (time.time() - 3600):
                return "Google Antigravity IDE"
            if cp_mtime > 0:
                return "VS Code + GitHub Copilot"
            if ag_mtime > 0:
                return "Google Antigravity IDE"
        except Exception:
            pass
        return "Google Antigravity IDE"

    def _resolve_client(self, client_name: Optional[str], user_agent: str) -> str:
        user_agent_lower = (user_agent or "").lower()
        if client_name and client_name != "AI Client":
            return client_name
        if "antigravity" in user_agent_lower:
            return "Google Antigravity IDE"
        if "copilot" in user_agent_lower or "code" in user_agent_lower:
            return "VS Code + GitHub Copilot"
        if "claude" in user_agent_lower:
            return "Claude Desktop"
        if "cursor" in user_agent_lower:
            return "Cursor"
        return self._infer_active_client()

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
            # Detect client from query param, User-Agent header, or active on-disk session
            user_agent = request.headers.get("user-agent") or ""
            resolved_client = self._resolve_client(client_name, user_agent)

            transport_conn_id = str(uuid.uuid4())
            queue: asyncio.Queue = asyncio.Queue()
            self._sse_queues[transport_conn_id] = queue

            # Find or bind the actual logical AI session for this connection
            logical_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
            self._connection_to_session[transport_conn_id] = logical_session.id
            self._connection_to_client[transport_conn_id] = resolved_client

            async def event_generator():
                try:
                    # Initial endpoint event per MCP SSE spec
                    endpoint_msg = f"/mcp/messages?sessionId={transport_conn_id}"
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
                    self._sse_queues.pop(transport_conn_id, None)
                    self._connection_to_session.pop(transport_conn_id, None)
                    self._connection_to_client.pop(transport_conn_id, None)

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

            # Map the transport connection ID to the persistent logical AI session ID
            resolved_client = self._connection_to_client.get(sessionId) or self._infer_active_client()

            # For tool calls from Copilot or Antigravity, dynamically re-validate to bind to the latest active chat session
            if body.get("method") == "tools/call" and ("Copilot" in resolved_client or "Antigravity" in resolved_client):
                active_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                logical_session_id = active_session.id
                self._connection_to_session[sessionId] = logical_session_id
            else:
                logical_session_id = self._connection_to_session.get(sessionId)
                if not logical_session_id:
                    logical_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                    logical_session_id = logical_session.id
                    self._connection_to_session[sessionId] = logical_session_id

            response = await self.gateway_proxy.handle_mcp_request(
                request_dict=body,
                session_id=logical_session_id,
                client_name=resolved_client,
                active_language=lang,
            )

            # If SSE queue exists for this transport connection, push response to SSE stream
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

            user_agent = request.headers.get("user-agent") or ""
            resolved_client = self._resolve_client(client_name, user_agent)

            if not sessionId or "Copilot" in resolved_client or "Antigravity" in resolved_client:
                logical_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                target_session_id = logical_session.id
            else:
                target_session_id = sessionId

            response = await self.gateway_proxy.handle_mcp_request(
                request_dict=body,
                session_id=target_session_id,
                client_name=resolved_client,
                active_language=lang,
            )
            return JSONResponse(response)
