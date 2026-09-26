"""OpenAI /v1/chat/completions function-call interception proxy."""

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.explainer.engine import ExplainerEngine
from backend.hitl.broker import DecisionStatus, HITLBroker
from backend.models.schemas import ActionLog
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityAssessment, SecurityEngine
from backend.storage.audit_store import AuditStore


class OpenAIProxyRouter:
    """
    Proxies and intercepts OpenAI-compatible /v1/chat/completions calls.
    Evaluates function / tool calls embedded in incoming messages or model outputs.
    """

    def __init__(
        self,
        security_engine: SecurityEngine,
        explainer_engine: ExplainerEngine,
        hitl_broker: HITLBroker,
        dlp_masker: DLPMasker,
        audit_store: AuditStore,
        upstream_openai_url: Optional[str] = None,
        default_language: str = "en",
    ):
        self.security_engine = security_engine
        self.explainer_engine = explainer_engine
        self.hitl_broker = hitl_broker
        self.dlp_masker = dlp_masker
        self.audit_store = audit_store
        self.upstream_openai_url = upstream_openai_url or os.environ.get(
            "UPSTREAM_OPENAI_URL", "https://api.openai.com/v1"
        )
        self.default_language = default_language
        self.router = APIRouter()
        self._setup_routes()

    def _setup_routes(self) -> None:
        @self.router.post("/v1/chat/completions")
        async def chat_completions(
            request: Request,
            authorization: Optional[str] = Header(None),
        ):
            """
            Intercepts chat completion requests containing tool_calls or function_call.
            Holds high-risk tool invocations via HITLBroker.
            """
            try:
                body = await request.json()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid JSON body")

            # Extract any tool calls embedded in request messages (agent execution loops)
            messages = body.get("messages", [])
            session_id = str(body.get("user") or uuid.uuid4())
            self._ensure_session(session_id, client_name="OpenAI Agent")

            # Capture user prompt to log full conversational chat history in SafeAI
            last_user_msg = next((m.get("content") for m in reversed(messages) if m.get("role") == "user"), None)
            if last_user_msg:
                user_msg_str = last_user_msg if isinstance(last_user_msg, str) else json.dumps(last_user_msg)
                sanitized_prompt = self.dlp_masker.redact_payload({"prompt": user_msg_str}).get("prompt", user_msg_str)
                action_id = f"act-chat-{uuid.uuid4().hex[:10]}"
                prompt_log = ActionLog(
                    id=action_id,
                    session_id=session_id,
                    tool_name="chat_message",
                    raw_payload=json.dumps({"prompt": sanitized_prompt}, ensure_ascii=False),
                    plain_language_explanation=f"User Prompt: {sanitized_prompt[:250]}" if len(sanitized_prompt) > 250 else f"User Prompt: {sanitized_prompt}",
                    language_code="en",
                    risk_score=5,
                    risk_factors=json.dumps(["CONVERSATION_HISTORY"]),
                    status="AUTO_APPROVED",
                    user_decision_by="AUTO_POLICY",
                    execution_result="Captured by SafeAI proxy.",
                )
                self.audit_store.log_action(prompt_log)

            # Check messages for assistant tool_calls needing inspection
            for msg in messages:
                if msg.get("role") == "assistant" and "tool_calls" in msg:
                    for tc in msg["tool_calls"]:
                        intercept_result = await self._intercept_tool_call(
                            tool_call=tc,
                            session_id=session_id,
                        )
                        if intercept_result.get("rejected"):
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "error": {
                                        "message": "Policy Denial: Tool call blocked by SafeAI governance proxy",
                                        "type": "security_policy_violation",
                                        "details": intercept_result,
                                    }
                                },
                            )

            # If upstream forwarding is requested and client provided authorization
            if authorization and self.upstream_openai_url and not self.upstream_openai_url.startswith("mock://"):
                return await self._forward_upstream(body, authorization, session_id)

            # Mock / local response for standalone testing
            return JSONResponse(
                {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": body.get("model", "safeai-intercept"),
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "SafeAI governance proxy: Request verified and permitted.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }
            )

    def _ensure_session(self, session_id: str, client_name: str) -> None:
        existing = self.audit_store.get_session_by_id(session_id)
        if not existing:
            from backend.models.schemas import SessionRecord
            self.audit_store.create_session(
                SessionRecord(id=session_id, client_name=client_name)
            )

    async def _intercept_tool_call(
        self, tool_call: Dict[str, Any], session_id: str
    ) -> Dict[str, Any]:
        """Evaluates an intercepted tool_call dictionary."""
        func = tool_call.get("function", {})
        tool_name = func.get("name", "unknown")
        raw_args_str = func.get("arguments", "{}")
        try:
            raw_args = json.loads(raw_args_str) if isinstance(raw_args_str, str) else raw_args_str
        except Exception:
            raw_args = {"raw": raw_args_str}

        action_id = f"act-oai-{uuid.uuid4().hex[:10]}"

        # 1. DLP redaction
        sanitized_args = self.dlp_masker.redact_payload(raw_args)
        sanitized_json = json.dumps(sanitized_args, ensure_ascii=False)

        # 2. Security Assessment
        assessment = self.security_engine.evaluate_payload(tool_name, sanitized_args)

        # 3. Explainer
        explanation = self.explainer_engine.generate_explanation(
            tool_name=tool_name,
            payload=sanitized_args,
            assessment=assessment,
            active_language=self.default_language,
        )

        # 4. Audit Log
        action_log = ActionLog(
            id=action_id,
            session_id=session_id,
            tool_name=tool_name,
            raw_payload=sanitized_json,
            plain_language_explanation=explanation,
            language_code=self.default_language,
            risk_score=assessment.risk_score,
            risk_factors=json.dumps(assessment.risk_factors),
            status="PENDING",
            user_decision_by="AUTO_POLICY" if assessment.risk_score < self.hitl_broker.approval_threshold else None,
        )
        self.audit_store.log_action(action_log)

        # 5. HITL Broker
        decision = await self.hitl_broker.intercept_and_hold(
            action_id=action_id,
            session_id=session_id,
            tool_name=tool_name,
            payload=sanitized_args,
            assessment=assessment,
            plain_explanation=explanation,
            active_language=self.default_language,
        )

        action_log.status = decision.value
        action_log.user_decision_by = "USER_MANUAL" if decision in (DecisionStatus.APPROVED, DecisionStatus.REJECTED) and action_log.user_decision_by is None else (action_log.user_decision_by or "AUTO_POLICY")
        self.audit_store.update_action(action_log)

        if decision in (DecisionStatus.REJECTED, DecisionStatus.TIMED_OUT):
            return {
                "rejected": True,
                "actionId": action_id,
                "riskScore": assessment.risk_score,
                "explanation": explanation,
                "status": decision.value,
            }

        return {"rejected": False, "actionId": action_id, "status": decision.value}

    async def _forward_upstream(
        self, body: Dict[str, Any], authorization: str, session_id: str
    ) -> JSONResponse:
        """Forwards request to upstream LLM API and intercepts response tool calls."""
        headers = {
            "Authorization": authorization,
            "Content-Type": "application/json",
        }
        url = f"{self.upstream_openai_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(url, json=body, headers=headers)
                data = resp.json()
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Upstream LLM error: {str(e)}")

        # Intercept tool_calls in choices
        choices = data.get("choices", [])
        for choice in choices:
            msg = choice.get("message", {})
            if "tool_calls" in msg:
                for tc in msg["tool_calls"]:
                    res = await self._intercept_tool_call(tc, session_id)
                    if res.get("rejected"):
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": {
                                    "message": "Policy Denial: Upstream tool call blocked by SafeAI governance proxy",
                                    "details": res,
                                }
                            },
                        )

        return JSONResponse(data)
