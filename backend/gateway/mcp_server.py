"""FastAPI router implementing MCP Streamable HTTP and SSE transports."""

import asyncio
import json
import uuid
from typing import Any, Dict, Optional

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

    def _resolve_client(
        self,
        client_name: Optional[str] = None,
        user_agent: str = "",
        body: Optional[Dict[str, Any]] = None,
    ) -> str:
        user_agent_lower = (user_agent or "").lower()
        if client_name and client_name != "AI Client":
            return "Hermes Agent" if "hermes" in client_name.lower() else client_name

        # Check clientInfo in JSON-RPC payload if available
        if body:
            client_info = (body.get("params") or {}).get("clientInfo") or {}
            c_name = client_info.get("name", "")
            if c_name:
                c_name_lower = c_name.lower()
                if "hermes" in c_name_lower:
                    return "Hermes Agent"
                if "antigravity" in c_name_lower:
                    return "Google Antigravity IDE"
                if "claude" in c_name_lower:
                    return "Claude Desktop"
                if "cursor" in c_name_lower:
                    return "Cursor"
                if "copilot" in c_name_lower or "code" in c_name_lower:
                    return "VS Code + GitHub Copilot"
                return c_name.title()

        if "hermes" in user_agent_lower:
            return "Hermes Agent"
        if "antigravity" in user_agent_lower:
            return "Google Antigravity IDE"
        if "copilot" in user_agent_lower or "code" in user_agent_lower:
            return "VS Code + GitHub Copilot"
        if "claude" in user_agent_lower:
            return "Claude Desktop"
        if "cursor" in user_agent_lower:
            return "Cursor"

        # Python MCP clients without explicit IDE headers are local agent runners like Hermes
        if "python" in user_agent_lower or "httpx" in user_agent_lower or "aiohttp" in user_agent_lower:
            return "Hermes Agent"

        return "MCP Client"

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

            user_agent = request.headers.get("user-agent") or ""
            client_info_name = (body.get("params") or {}).get("clientInfo", {}).get("name")
            if client_info_name:
                resolved_client = self._resolve_client(client_info_name, user_agent, body=body)
                self._connection_to_client[sessionId] = resolved_client

            # Map the transport connection ID to the persistent logical AI session ID
            resolved_client = self._connection_to_client.get(sessionId) or self._resolve_client(None, user_agent, body=body)

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
            resolved_client = self._resolve_client(client_name, user_agent, body=body)

            # Separate session for distinct client connections to prevent cross-merging
            conn_key = request.headers.get("mcp-session-id") or sessionId or request.headers.get("x-session-id")
            if conn_key and conn_key in self._connection_to_session:
                target_session_id = self._connection_to_session[conn_key]
            else:
                logical_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                target_session_id = logical_session.id
                if conn_key:
                    self._connection_to_session[conn_key] = target_session_id
                    self._connection_to_client[conn_key] = resolved_client

            response = await self.gateway_proxy.handle_mcp_request(
                request_dict=body,
                session_id=target_session_id,
                client_name=resolved_client,
                active_language=lang,
            )
            return JSONResponse(response)
