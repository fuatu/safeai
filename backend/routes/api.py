import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.explainer.engine import ExplainerEngine
from backend.gateway.client_configs import get_all_client_configs
from backend.hitl.broker import HITLBroker
from backend.models.schemas import ActionLog, PolicyRule, SessionRecord, SystemConfig, ToolSetting
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


class DecisionRequest(BaseModel):
    actionId: str
    decision: str  # "APPROVE" or "DENY"
    notes: Optional[str] = None


class InterceptRequest(BaseModel):
    command: Optional[str] = None
    tool_name: str = "bash"
    payload: Optional[Dict[str, Any]] = None
    client_name: str = "Terminal Interceptor"
    session_id: Optional[str] = None
    timeout_seconds: Optional[int] = None


class ConfigUpdateRequest(BaseModel):
    approval_threshold: Optional[int] = None
    active_language: Optional[str] = None
    explainer_mode: Optional[str] = None
    dlp_enabled: Optional[bool] = None
    approval_timeout_seconds: Optional[int] = None


def create_api_router(
    audit_store: AuditStore,
    hitl_broker: HITLBroker,
    security_engine: SecurityEngine,
    current_config: SystemConfig,
    copilot_syncer: Optional[Any] = None,
    explainer_engine: Optional[ExplainerEngine] = None,
) -> APIRouter:
    router = APIRouter(prefix="/api")
    explainer = explainer_engine or ExplainerEngine()

    @router.post("/eval/intercept")
    async def intercept_execution(body: InterceptRequest) -> Dict[str, Any]:
        """
        Pre-execution gate endpoint: Evaluates commands or tool calls before execution.
        If risk < threshold: Auto-approves and returns {"decision": "ALLOW"}.
        If risk >= threshold: Suspends execution, broadcasts to Web Panel, and waits
        for human approval/denial or timeout.
        """
        payload = body.payload.copy() if body.payload else {}
        if body.command:
            payload["command"] = body.command

        # 1. Run Security Evaluation across CIA Triad
        assessment = security_engine.evaluate_payload(body.tool_name, payload)

        # 2. Generate multilingual explanation
        explanation = explainer.generate_explanation(
            tool_name=body.tool_name,
            payload=payload,
            assessment=assessment,
            active_language=current_config.active_language,
        )

        threshold = current_config.approval_threshold

        # Ensure session exists
        session_id = body.session_id or f"gate-sess-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        if not audit_store.get_session_by_id(session_id):
            audit_store.create_session(
                SessionRecord(
                    id=session_id,
                    client_name=body.client_name,
                    title=f"{body.client_name}: Intercepted Shell",
                    started_at=datetime.now(timezone.utc),
                )
            )

        action_id = f"gate-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Log initial action
        log_entry = ActionLog(
            id=action_id,
            session_id=session_id,
            timestamp=now,
            tool_name=body.tool_name,
            raw_payload=json.dumps(payload, ensure_ascii=False),
            plain_language_explanation=explanation,
            language_code=current_config.active_language or "en",
            risk_score=assessment.risk_score,
            risk_factors=json.dumps(assessment.risk_factors),
            status="PENDING" if assessment.risk_score >= threshold else "AUTO_APPROVED",
            user_decision_by="AUTO_POLICY" if assessment.risk_score < threshold else None,
            execution_result="Approved automatically by SafeAI security policy." if assessment.risk_score < threshold else None,
        )
        audit_store.log_action(log_entry)

        # Intercept and hold via broker
        decision_status = await hitl_broker.intercept_and_hold(
            action_id=action_id,
            session_id=session_id,
            tool_name=body.tool_name,
            payload=payload,
            assessment=assessment,
            plain_explanation=explanation,
            active_language=current_config.active_language or "en",
            timeout_seconds=body.timeout_seconds or current_config.approval_timeout_seconds,
            custom_threshold=threshold,
        )

        notes = hitl_broker.get_decision_notes(action_id)

        if decision_status.value in ("AUTO_APPROVED", "APPROVED"):
            if decision_status.value == "APPROVED":
                log_entry.status = "APPROVED"
                log_entry.user_decision_by = "USER_MANUAL"
                log_entry.decision_notes = notes
                audit_store.update_action(log_entry)

            return {
                "decision": "ALLOW",
                "action_id": action_id,
                "user_decision_by": "USER_MANUAL" if decision_status.value == "APPROVED" else "AUTO_POLICY",
                "notes": notes,
                "risk_score": assessment.risk_score,
                "risk_factors": assessment.risk_factors,
                "integrity_score": assessment.integrity_score,
                "confidentiality_score": assessment.confidentiality_score,
                "availability_score": assessment.availability_score,
                "explanation": explanation,
            }
        else:
            log_entry.status = "REJECTED" if decision_status.value == "REJECTED" else "TIMED_OUT"
            log_entry.user_decision_by = "USER_MANUAL" if decision_status.value == "REJECTED" else "AUTO_TIMEOUT"
            log_entry.decision_notes = notes or ("Timed out waiting for approval" if decision_status.value == "TIMED_OUT" else "Denied by human supervisor")
            audit_store.update_action(log_entry)

            return {
                "decision": "BLOCK",
                "action_id": action_id,
                "reason": log_entry.decision_notes,
                "risk_score": assessment.risk_score,
                "risk_factors": assessment.risk_factors,
                "explanation": explanation,
            }



    @router.post("/copilot/sync")
    def sync_copilot_chat() -> Dict[str, Any]:
        """Scans local VS Code storage and synchronizes Copilot chat history."""
        if not copilot_syncer:
            return {"status": "not_configured", "synced_turns": 0}
        count = copilot_syncer.sync_latest()
        return {"status": "success", "synced_turns": count}

    # -------------------------------------------------------------
    # Approvals & HITL Management
    # -------------------------------------------------------------

    @router.get("/approvals/pending")
    def get_pending_approvals() -> List[Dict[str, Any]]:
        """Returns all currently suspended approvals."""
        return hitl_broker.get_pending_approvals()

    @router.post("/approvals/decide")
    async def decide_approval(body: DecisionRequest):
        """Submits human approval decision via REST."""
        success = await hitl_broker.submit_decision(
            action_id=body.actionId,
            decision=body.decision,
            notes=body.notes,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Pending action not found or already resolved")
        return {"status": "success", "actionId": body.actionId, "decision": body.decision}

    # -------------------------------------------------------------
    # Sessions & Audit Logs
    # -------------------------------------------------------------

    @router.get("/sessions")
    def list_sessions(limit: int = Query(50, ge=1, le=200)) -> List[SessionRecord]:
        return audit_store.list_sessions(limit=limit)

    @router.get("/sessions/{session_id}")
    def get_session(session_id: str) -> SessionRecord:
        rec = audit_store.get_session_by_id(session_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Session not found")
        return rec

    @router.get("/sessions/{session_id}/actions")
    def list_session_actions(
        session_id: str, limit: int = Query(100, ge=1, le=500)
    ) -> List[ActionLog]:
        return audit_store.list_actions(session_id=session_id, limit=limit)

    @router.get("/logs/export")
    def export_audit_logs(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Exports sanitized logs with zero plaintext secrets."""
        return audit_store.export_logs(session_id=session_id)

    # -------------------------------------------------------------
    # Settings & Policy Hot-Reload (Req 5.4)
    # -------------------------------------------------------------

    @router.get("/settings")
    def get_settings() -> SystemConfig:
        return current_config

    @router.put("/settings")
    def update_settings(updates: ConfigUpdateRequest) -> SystemConfig:
        """Hot-reloads system settings without restart."""
        if updates.approval_threshold is not None:
            current_config.approval_threshold = updates.approval_threshold
            hitl_broker.set_threshold(updates.approval_threshold)

        if updates.approval_timeout_seconds is not None:
            current_config.approval_timeout_seconds = updates.approval_timeout_seconds
            hitl_broker.set_timeout(updates.approval_timeout_seconds)

        if updates.active_language is not None:
            current_config.active_language = updates.active_language
            explainer.default_language = updates.active_language

        if updates.explainer_mode is not None:
            current_config.explainer_mode = updates.explainer_mode

        if updates.dlp_enabled is not None:
            current_config.dlp_enabled = updates.dlp_enabled

        return current_config

    # -------------------------------------------------------------
    # Policy Rules CRUD
    # -------------------------------------------------------------

    @router.get("/policy/rules")
    def list_policy_rules() -> List[PolicyRule]:
        return audit_store.get_policy_rules(active_only=False)

    @router.post("/policy/rules")
    def add_policy_rule(rule: PolicyRule) -> PolicyRule:
        created = audit_store.add_policy_rule(rule)
        security_engine.set_policy_rules(audit_store.get_policy_rules(active_only=True))
        return created

    @router.put("/policy/rules")
    def update_policy_rule(rule: PolicyRule) -> PolicyRule:
        updated = audit_store.update_policy_rule(rule)
        security_engine.set_policy_rules(audit_store.get_policy_rules(active_only=True))
        return updated

    @router.delete("/policy/rules/{rule_id}")
    def delete_policy_rule(rule_id: str):
        success = audit_store.delete_policy_rule(rule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        security_engine.set_policy_rules(audit_store.get_policy_rules(active_only=True))
        return {"status": "deleted", "ruleId": rule_id}

    # -------------------------------------------------------------
    # Tool Settings & Governance (Req 8.1 - 8.5)
    # -------------------------------------------------------------

    @router.get("/tools/settings")
    def list_tool_settings() -> List[ToolSetting]:
        return audit_store.get_tool_settings()

    @router.get("/tools/settings/{tool_name}")
    def get_tool_setting(tool_name: str) -> ToolSetting:
        setting = audit_store.get_tool_setting(tool_name)
        if not setting:
            raise HTTPException(status_code=404, detail="Tool setting not found")
        return setting

    @router.post("/tools/settings")
    def upsert_tool_setting(setting: ToolSetting) -> ToolSetting:
        return audit_store.add_or_update_tool_setting(setting)

    @router.delete("/tools/settings/{tool_name}")
    def delete_tool_setting(tool_name: str):
        success = audit_store.delete_tool_setting(tool_name)
        if not success:
            raise HTTPException(status_code=404, detail="Tool setting not found")
        return {"status": "deleted", "toolName": tool_name}

    # -------------------------------------------------------------
    # AI Client Connection Configurations (Req 1.1, 7.3)
    # -------------------------------------------------------------

    @router.get("/client-configs")
    def get_client_configs(
        port: int = Query(8080, ge=1, le=65535),
        host: str = Query("localhost"),
    ) -> Dict[str, Any]:
        """Returns ready-to-use AI client configuration snippets and guides."""
        return get_all_client_configs(port=port, host=host)

    return router
