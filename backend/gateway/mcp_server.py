"""FastAPI router implementing MCP Streamable HTTP and SSE transports."""

import asyncio
import json
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from backend.gateway.client_resolver import canonicalize_client_name
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
        existing_client: Optional[str] = None,
    ) -> str:
        # 1. Explicit client_name query param has top priority
        if client_name:
            canon = canonicalize_client_name(client_name)
            if canon:
                return canon

        # 2. If an existing client was already resolved and is specific, preserve it
        if existing_client and existing_client not in ("MCP Client", "AI Client"):
            return existing_client

        # 3. Check clientInfo in JSON-RPC payload if available
        if body:
            client_info = (body.get("params") or {}).get("clientInfo") or {}
            c_name = client_info.get("name", "")
            if c_name:
                canon = canonicalize_client_name(c_name)
                if canon:
                    return canon

        # 4. Check User-Agent headers
        user_agent_lower = (user_agent or "").lower()
        if "antigravity" in user_agent_lower or "gemini" in user_agent_lower:
            return "Google Antigravity IDE"
        if "copilot" in user_agent_lower or "code" in user_agent_lower or "vscode" in user_agent_lower:
            return "VS Code + GitHub Copilot"
        if "hermes" in user_agent_lower:
            return "Hermes Agent"
        if "claude" in user_agent_lower:
            return "Claude Desktop"
        if "cursor" in user_agent_lower or "windsurf" in user_agent_lower:
            return "Cursor"

        # Python / httpx clients without explicit headers are local agent runners like Hermes
        if any(sig in user_agent_lower for sig in ("python", "httpx", "aiohttp", "urllib")):
            return "Hermes Agent"

        return existing_client or "MCP Client"

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
                    # Initial endpoint event per MCP SSE spec with client_name preserved
                    import urllib.parse
                    encoded_client = urllib.parse.quote(resolved_client)
                    endpoint_msg = f"/mcp/messages?sessionId={transport_conn_id}&client_name={encoded_client}"
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
            client_name: Optional[str] = Query(None, description="Active client name"),
            lang: Optional[str] = Query(None, description="Active language code"),
        ):
            """Receives client JSON-RPC messages and routes them through GatewayProxy."""
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            user_agent = request.headers.get("user-agent") or ""
            existing_client = self._connection_to_client.get(sessionId)
            resolved_client = self._resolve_client(
                client_name=client_name,
                user_agent=user_agent,
                body=body,
                existing_client=existing_client,
            )
            self._connection_to_client[sessionId] = resolved_client

            # Map the transport connection ID to the persistent logical AI session ID
            logical_session_id = self._connection_to_session.get(sessionId)
            if not logical_session_id:
                logical_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                logical_session_id = logical_session.id
                self._connection_to_session[sessionId] = logical_session_id

            # For tool calls from Copilot or Antigravity, dynamically re-validate to bind to the latest active chat session
            if body.get("method") == "tools/call" and ("Copilot" in resolved_client or "Antigravity" in resolved_client):
                active_session = self.gateway_proxy.resolve_active_session_for_client(resolved_client)
                logical_session_id = active_session.id
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
            client_name: Optional[str] = Query(None, description="Client name query parameter"),
            lang: Optional[str] = Query(None),
        ):
            """Direct Streamable HTTP JSON-RPC endpoint for MCP clients."""
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            user_agent = request.headers.get("user-agent") or ""
            conn_key = request.headers.get("mcp-session-id") or sessionId or request.headers.get("x-session-id")
            existing_client = self._connection_to_client.get(conn_key) if conn_key else None
            resolved_client = self._resolve_client(
                client_name=client_name,
                user_agent=user_agent,
                body=body,
                existing_client=existing_client,
            )

            # Separate session for distinct client connections to prevent cross-merging
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
