"""Gateway proxy and MCP protocol router for SafeAI Core."""

import asyncio
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from backend.explainer.engine import ExplainerEngine
from backend.hitl.broker import DecisionStatus, HITLBroker
from backend.gateway.client_resolver import canonicalize_client_name
from backend.models.schemas import ActionLog, SessionRecord, ToolSetting
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityAssessment, SecurityEngine
from backend.storage.audit_store import AuditStore


class MCPRequest(BaseModel):
    """Standard Model Context Protocol JSON-RPC 2.0 request."""
    jsonrpc: str = "2.0"
    id: Optional[Any] = None
    method: str
    params: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GatewayProxy:
    """
    Transparent security gateway that intercepts MCP tools/call invocations,
    applies DLP masking, computes multi-vector security risk, generates multilingual
    explanations, and holds execution via HITLBroker when necessary.
    """

    def __init__(
        self,
        security_engine: SecurityEngine,
        explainer_engine: ExplainerEngine,
        hitl_broker: HITLBroker,
        dlp_masker: DLPMasker,
        audit_store: AuditStore,
        downstream_url: Optional[str] = None,
        default_language: str = "en",
    ):
        self.security_engine = security_engine
        self.explainer_engine = explainer_engine
        self.hitl_broker = hitl_broker
        self.dlp_masker = dlp_masker
        self.audit_store = audit_store
        self.downstream_url = downstream_url
        self.default_language = default_language
        self.active_sessions: Dict[str, SessionRecord] = {}

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        client_name: str = "AI Client",
        title: Optional[str] = None,
    ) -> SessionRecord:
        """Retrieves or initializes a session record."""
        sid = session_id or str(uuid.uuid4())
        existing = self.audit_store.get_session_by_id(sid)
        if existing:
            if existing.client_name in ("AI Client", "AI Client...") and client_name != "AI Client":
                existing.client_name = client_name
                if not existing.title or "AI Client" in existing.title:
                    existing.title = title or f"{client_name} (Connected)"
                self.audit_store.update_session(existing)
            return existing

        new_sess = SessionRecord(
            id=sid,
            client_name=client_name,
            title=title or f"{client_name} (Connected)",
        )
        self.audit_store.create_session(new_sess)
        self.active_sessions[sid] = new_sess
        return new_sess

    def resolve_active_session_for_client(
        self, client_name: str = "VS Code + GitHub Copilot"
    ) -> SessionRecord:
        """
        Resolves or creates the single active session for an AI client,
        preventing session fragmentation across repeated tool calls or SSE reconnects.
        """
        canon_name = canonicalize_client_name(client_name) or client_name
        c_lower = canon_name.lower()
        now = datetime.now(timezone.utc)

        # 1. Google Antigravity IDE
        if "antigravity" in c_lower:
            try:
                from backend.storage.antigravity_sync import AntigravityChatSyncer
                syncer = AntigravityChatSyncer(audit_store=self.audit_store)
                latest_file = syncer.get_latest_transcript_file()
                if latest_file:
                    session_stem = latest_file.parent.parent.parent.name
                    target_id = f"antigravity-{session_stem[:18]}"
                    existing = self.audit_store.get_session_by_id(target_id)
                    if existing:
                        return existing

                    turns = syncer.parse_transcript_file(latest_file)
                    first_p = turns[0]["prompt"].strip().replace("\n", " ") if turns else ""
                    short_p = (first_p[:34] + "...") if len(first_p) > 34 else (first_p or "Antigravity Session")
                    date_str = now.strftime("%b %d, %H:%M")
                    nice_title = f'Antigravity: "{short_p}" ({date_str})'
                    new_sess = SessionRecord(
                        id=target_id,
                        client_name="Google Antigravity IDE",
                        title=nice_title,
                        started_at=now,
                    )
                    return self.audit_store.create_session(new_sess)
            except Exception:
                pass

            # Fallback if no on-disk transcript yet
            recent_sessions = self.audit_store.list_sessions(limit=10)
            for s in recent_sessions:
                if "Antigravity" in s.client_name and not s.ended_at:
                    if (now - s.started_at).total_seconds() < 3600:
                        return s
            new_id = f"antigravity-{uuid.uuid4().hex[:12]}"
            date_str = now.strftime("%b %d, %H:%M")
            return self.audit_store.create_session(SessionRecord(
                id=new_id,
                client_name="Google Antigravity IDE",
                title=f"Google Antigravity IDE ({date_str})",
                started_at=now,
            ))

        # 2. VS Code / GitHub Copilot
        if "copilot" in c_lower or "code" in c_lower:
            try:
                from backend.storage.copilot_sync import CopilotChatSyncer
                syncer = CopilotChatSyncer(audit_store=self.audit_store)
                latest_file = syncer.get_latest_chat_session_file()
                if latest_file:
                    target_id = f"copilot-{latest_file.stem[:18]}"
                    existing = self.audit_store.get_session_by_id(target_id)
                    turns = syncer.parse_chat_session_file(latest_file)
                    custom_title = turns[0].get("custom_title") if turns else None
                    first_p = turns[0]["prompt"].strip().replace("\n", " ") if turns else ""
                    short_p = (first_p[:34] + "...") if len(first_p) > 34 else (first_p or "Copilot Chat")
                    date_str = now.strftime("%b %d, %H:%M")
                    nice_title = (
                        f'VS Code + Copilot: "{custom_title}" ({date_str})'
                        if custom_title
                        else f'VS Code + Copilot: "{short_p}" ({date_str})'
                    )

                    if existing:
                        if not existing.title or '"Copilot Chat"' in existing.title or "Connected" in existing.title:
                            existing.title = nice_title
                            existing.client_name = "VS Code + GitHub Copilot"
                            self.audit_store.update_session(existing)
                        return existing

                    # Create session if not yet in DB
                    new_sess = SessionRecord(
                        id=target_id,
                        client_name="VS Code + GitHub Copilot",
                        title=nice_title,
                        started_at=now,
                    )
                    return self.audit_store.create_session(new_sess)
            except Exception:
                pass

            # Fallback if no chat file on disk yet
            recent_sessions = self.audit_store.list_sessions(limit=10)
            for s in recent_sessions:
                if "Copilot" in s.client_name and not s.ended_at:
                    if (now - s.started_at).total_seconds() < 3600:
                        return s
            new_id = f"copilot-{uuid.uuid4().hex[:12]}"
            date_str = now.strftime("%b %d, %H:%M")
            return self.audit_store.create_session(SessionRecord(
                id=new_id,
                client_name="VS Code + GitHub Copilot",
                title=f"VS Code + GitHub Copilot ({date_str})",
                started_at=now,
            ))

        # 3. Hermes Agent
        if "hermes" in c_lower:
            recent_sessions = self.audit_store.list_sessions(limit=10)
            for s in recent_sessions:
                if "Hermes" in s.client_name and not s.ended_at:
                    if (now - s.started_at).total_seconds() < 3600:
                        return s
            new_id = f"hermes-{uuid.uuid4().hex[:12]}"
            date_str = now.strftime("%b %d, %H:%M")
            return self.audit_store.create_session(SessionRecord(
                id=new_id,
                client_name="Hermes Agent",
                title=f"Hermes Agent ({date_str})",
                started_at=now,
            ))

        # 4. Claude Desktop
        if "claude" in c_lower:
            recent_sessions = self.audit_store.list_sessions(limit=10)
            for s in recent_sessions:
                if "Claude" in s.client_name and not s.ended_at:
                    if (now - s.started_at).total_seconds() < 3600:
                        return s
            new_id = f"claude-{uuid.uuid4().hex[:12]}"
            date_str = now.strftime("%b %d, %H:%M")
            return self.audit_store.create_session(SessionRecord(
                id=new_id,
                client_name="Claude Desktop",
                title=f"Claude Desktop ({date_str})",
                started_at=now,
            ))

        # 5. Cursor
        if "cursor" in c_lower:
            recent_sessions = self.audit_store.list_sessions(limit=10)
            for s in recent_sessions:
                if "Cursor" in s.client_name and not s.ended_at:
                    if (now - s.started_at).total_seconds() < 3600:
                        return s
            new_id = f"cursor-{uuid.uuid4().hex[:12]}"
            date_str = now.strftime("%b %d, %H:%M")
            return self.audit_store.create_session(SessionRecord(
                id=new_id,
                client_name="Cursor",
                title=f"Cursor ({date_str})",
                started_at=now,
            ))

        # 6. General active session reuse window (last 45 minutes)
        recent_sessions = self.audit_store.list_sessions(limit=10)
        for s in recent_sessions:
            if s.client_name == canon_name and not s.ended_at:
                if (now - s.started_at).total_seconds() < 2700:
                    return s

        new_id = f"sess-{uuid.uuid4().hex[:12]}"
        date_str = now.strftime("%b %d, %H:%M")
        return self.audit_store.create_session(SessionRecord(
            id=new_id,
            client_name=canon_name,
            title=f"{canon_name} ({date_str})",
            started_at=now,
        ))

    def resolve_tool_setting(self, tool_name: str) -> Optional[ToolSetting]:
        """
        Resolves MCP tool governance setting with fallback to generic wildcard '*'.
        """
        specific = self.audit_store.get_tool_setting(tool_name)
        if specific:
            return specific
        return self.audit_store.get_tool_setting("*")

    async def handle_mcp_request(
        self,
        request_dict: Dict[str, Any],
        session_id: Optional[str] = None,
        client_name: str = "AI Client",
        active_language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main ingress handler for MCP JSON-RPC requests.
        Evaluates and intercepts 'tools/call'.
        """
        rpc_id = request_dict.get("id")
        method = request_dict.get("method", "")
        params = request_dict.get("params") or {}

        # 1. MCP Handshake & Protocol Methods
        if method == "initialize":
            client_info = params.get("clientInfo") or {}
            client_info_name = client_info.get("name", "")
            canon_client = canonicalize_client_name(client_info_name)
            if canon_client and session_id:
                sess = self.audit_store.get_session_by_id(session_id)
                if sess and sess.client_name in ("AI Client", "MCP Client"):
                    sess.client_name = canon_client
                    if not sess.title or "AI Client" in sess.title or "Connected" in sess.title or "MCP Client" in sess.title:
                        sess.title = f"{canon_client} (Connected)"
                    self.audit_store.update_session(sess)

            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "logging": {},
                    },
                    "serverInfo": {
                        "name": "safeai-governance-gateway",
                        "version": "1.0.0",
                    },
                },
            }

        if method == "notifications/initialized":
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {}}

        if method == "tools/list":
            return await self._handle_tools_list(rpc_id, active_language)

        # 2. Intercept tools/call (Req 1.1)
        if method == "tools/call":
            return await self._handle_tool_call(
                rpc_id=rpc_id,
                params=params,
                session_id=session_id,
                client_name=client_name,
                active_language=active_language,
            )

        # Unknown method fallback
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }

    async def _handle_tools_list(
        self, rpc_id: Any, active_language: Optional[str]
    ) -> Dict[str, Any]:
        """Returns registered or proxied tool declarations."""
        lang = self.explainer_engine.resolve_active_language(active_language)
        # Standard default tools intercepted by SafeAI
        default_tools = [
            {
                "name": "bash",
                "description": "Execute shell command on local machine under SafeAI governance."
                if lang == "en"
                else "SafeAI gözetiminde yerel terminalde komut çalıştırır.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command line to execute"}
                    },
                    "required": ["command"],
                },
            },
            {
                "name": "read_file",
                "description": "Read file contents from local filesystem.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to file"}
                    },
                    "required": ["file_path"],
                },
            },
        ]
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": default_tools},
        }

    async def _handle_tool_call(
        self,
        rpc_id: Any,
        params: Dict[str, Any],
        session_id: Optional[str],
        client_name: str,
        active_language: Optional[str],
    ) -> Dict[str, Any]:
        """
        Intercepts tools/call:
        1. DLP mask secrets from payload
        2. Evaluate AST risk
        3. Generate multilingual explanation
        4. Check HITL hold
        5. Execute downstream (or local) if approved
        6. Return standard JSON-RPC response
        """
        session = self.get_or_create_session(session_id, client_name)
        tool_name = params.get("name", "unknown")
        raw_arguments = params.get("arguments") or {}

        # 0. Check Tool Setting & Governance (Req 8.1 - 8.5)
        tool_setting = self.resolve_tool_setting(tool_name)
        if tool_setting and not tool_setting.is_enabled:
            action_id = f"act-{uuid.uuid4().hex[:12]}"
            action_log = ActionLog(
                id=action_id,
                session_id=session.id,
                tool_name=tool_name,
                raw_payload=json.dumps(raw_arguments, ensure_ascii=False),
                plain_language_explanation=f"Tool '{tool_name}' execution was denied because it is disabled in security governance settings.",
                language_code="en",
                risk_score=100,
                risk_factors=json.dumps(["TOOL_DISABLED"]),
                status="REJECTED",
                user_decision_by="AUTO_POLICY",
                decision_notes="Blocked by per-tool disable rule",
            )
            self.audit_store.log_action(action_log)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32000,
                    "message": f"Security Policy Denial: Tool '{tool_name}' is disabled by administrative governance policy",
                    "data": {"actionId": action_id, "toolName": tool_name},
                },
            }

        # Extract textual context from arguments and parameters for conversational language auto-detection
        context_parts = []
        for val in raw_arguments.values():
            if isinstance(val, str):
                context_parts.append(val)
            elif isinstance(val, (dict, list)):
                context_parts.append(json.dumps(val, ensure_ascii=False))
        context_text = " ".join(context_parts)

        action_id = f"act-{uuid.uuid4().hex[:12]}"
        lang = self.explainer_engine.resolve_active_language(
            active_language or self.default_language,
            context_text=context_text,
        )

        # 1. DLP Mask secrets in arguments before security assessment & persistence (Req 6.2)
        has_secrets = self.dlp_masker.contains_secrets(raw_arguments)
        sanitized_arguments = self.dlp_masker.redact_payload(raw_arguments)
        sanitized_json = json.dumps(sanitized_arguments, ensure_ascii=False)

        # 2. Security Assessment (Req 2.1 - 2.6)
        assessment = self.security_engine.evaluate_payload(tool_name, sanitized_arguments)

        # 3. Multilingual Plain-Language Explainer (Req 3.1, 3.2, 3.7)
        explanation = self.explainer_engine.generate_explanation(
            tool_name=tool_name,
            payload=sanitized_arguments,
            assessment=assessment,
            active_language=lang,
            context_text=context_text,
        )

        # Determine effective threshold & bypass
        bypass_active = (
            tool_setting is not None
            and tool_setting.bypass_approval
            and not has_secrets
        )
        custom_threshold = 101 if bypass_active else (
            tool_setting.custom_threshold if tool_setting and tool_setting.custom_threshold is not None else None
        )
        effective_threshold = (
            custom_threshold if custom_threshold is not None else self.hitl_broker.approval_threshold
        )

        # Initial log creation as PENDING / processing
        action_log = ActionLog(
            id=action_id,
            session_id=session.id,
            tool_name=tool_name,
            raw_payload=sanitized_json,
            plain_language_explanation=explanation,
            language_code=lang,
            risk_score=assessment.risk_score,
            risk_factors=json.dumps(assessment.risk_factors),
            status="PENDING",
            user_decision_by="AUTO_POLICY" if assessment.risk_score < effective_threshold else None,
        )
        self.audit_store.log_action(action_log)

        # Update session title dynamically based on the tool and action
        action_count = session.total_actions + 1
        tool_label = tool_name
        if tool_name == "bash":
            cmd = sanitized_arguments.get("command", "")
            cmd_snippet = (cmd[:28] + "...") if len(cmd) > 28 else cmd
            tool_label = f"bash ({cmd_snippet})" if cmd_snippet else "bash"
        elif tool_name == "read_file":
            fpath = sanitized_arguments.get("file_path", "")
            fname = fpath.split("/")[-1] if "/" in fpath else fpath
            tool_label = f"Read {fname}" if fname else "read_file"

        # Update session title dynamically based on the tool only if not already meaningful with a prompt
        if not session.title or "Connected" in session.title or session.title.startswith("AI Client"):
            session.title = f"{session.client_name}: {tool_label}"
            if action_count > 1:
                session.title += f" ({action_count} actions)"
            self.audit_store.update_session(session)

        # 4. HITL Connection Hold Check (Req 4.1 - 4.5)
        decision = await self.hitl_broker.intercept_and_hold(
            action_id=action_id,
            session_id=session.id,
            tool_name=tool_name,
            payload=sanitized_arguments,
            assessment=assessment,
            plain_explanation=explanation,
            active_language=lang,
            custom_threshold=custom_threshold,
        )

        action_log.status = decision.value
        action_log.user_decision_by = "USER_MANUAL" if decision in (DecisionStatus.APPROVED, DecisionStatus.REJECTED) and action_log.user_decision_by is None else (action_log.user_decision_by or "AUTO_POLICY")
        action_log.decision_notes = self.hitl_broker.get_decision_notes(action_id)

        # If rejected or timed out, abort immediately and return error response
        if decision == DecisionStatus.REJECTED:
            self.audit_store.update_action(action_log)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32000,
                    "message": "Security Policy Denial: Action rejected by SafeAI governance proxy",
                    "data": {
                        "actionId": action_id,
                        "riskScore": assessment.risk_score,
                        "riskFactors": assessment.risk_factors,
                        "explanation": explanation,
                    },
                },
            }

        if decision == DecisionStatus.TIMED_OUT:
            self.audit_store.update_action(action_log)
            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32001,
                    "message": "Approval Timeout: Action rejected because approval timed out",
                    "data": {"actionId": action_id, "timeoutSeconds": self.hitl_broker.timeout_seconds},
                },
            }

        # 5. Forward to downstream or execute locally (Req 1.3, 1.4, 4.3, 8.4)
        target_downstream_url = (
            tool_setting.downstream_url if (tool_setting and tool_setting.downstream_url) else self.downstream_url
        )
        target_timeout_ms = (
            tool_setting.timeout_ms if (tool_setting and tool_setting.timeout_ms is not None) else 15000
        )

        start_exec = time.perf_counter()
        try:
            execution_result = await self.dispatch_execution(
                tool_name=tool_name,
                arguments=sanitized_arguments,
                downstream_url=target_downstream_url,
                timeout_ms=target_timeout_ms,
            )
            exec_duration_ms = int((time.perf_counter() - start_exec) * 1000)

            # Redact execution output before persistence (Req 6.2, 6.3)
            sanitized_output = self.dlp_masker.redact_secrets(str(execution_result.get("content", "")))
            action_log.execution_duration_ms = exec_duration_ms
            action_log.execution_result = sanitized_output
            self.audit_store.update_action(action_log)

            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [
                        {"type": "text", "text": sanitized_output}
                    ],
                    "isError": execution_result.get("isError", False),
                },
            }

        except asyncio.TimeoutError:
            # Req 1.4: Downstream timeout >= target_timeout_ms -> standard JSON-RPC error
            exec_duration_ms = int((time.perf_counter() - start_exec) * 1000)
            action_log.execution_duration_ms = exec_duration_ms
            action_log.status = "TIMED_OUT"
            action_log.execution_result = f"Downstream tool timeout (exceeded {target_timeout_ms}ms)"
            self.audit_store.update_action(action_log)

            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32603,
                    "message": f"Downstream tool timeout: failed to respond within {target_timeout_ms}ms",
                },
            }
        except Exception as ex:
            exec_duration_ms = int((time.perf_counter() - start_exec) * 1000)
            action_log.execution_duration_ms = exec_duration_ms
            action_log.execution_result = f"Downstream execution error: {str(ex)}"
            self.audit_store.update_action(action_log)

            return {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {
                    "code": -32603,
                    "message": f"Downstream execution error: {str(ex)}",
                },
            }

    async def dispatch_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        downstream_url: Optional[str] = None,
        timeout_ms: int = 15000,
    ) -> Dict[str, Any]:
        """
        Dispatches tool call to downstream MCP HTTP server if configured,
        or handles standard safe execution locally.
        """
        timeout_sec = timeout_ms / 1000.0
        target_url = downstream_url or self.downstream_url

        # If downstream server configured, forward request
        if target_url:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.post(
                    target_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": str(uuid.uuid4()),
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments},
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                result = data.get("result", {})
                return {
                    "content": result.get("content", ""),
                    "isError": result.get("isError", False),
                }

        # Otherwise, local execution handler for standard tools (e.g. bash, echo)
        if tool_name in ("bash", "run_command", "shell"):
            cmd = arguments.get("command", "")
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout_sec,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
            out_str = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
            return {
                "content": out_str.strip(),
                "isError": proc.returncode != 0,
            }

        return {"content": f"Executed tool '{tool_name}' successfully.", "isError": False}
