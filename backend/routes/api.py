"""REST API endpoints for Web Panel management and policy hot-reloading."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.gateway.client_configs import get_all_client_configs
from backend.hitl.broker import HITLBroker
from backend.models.schemas import ActionLog, PolicyRule, SessionRecord, SystemConfig, ToolSetting
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


class DecisionRequest(BaseModel):
    actionId: str
    decision: str  # "APPROVE" or "DENY"
    notes: Optional[str] = None


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
) -> APIRouter:
    router = APIRouter(prefix="/api")

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
