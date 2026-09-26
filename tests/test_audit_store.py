"""Tests for SQLModel schemas and AuditStore."""

import os
import tempfile
import pytest
from datetime import datetime, timezone

from backend.models.schemas import ActionLog, PolicyRule, SessionRecord, SystemConfig
from backend.storage.audit_store import AuditStore


@pytest.fixture
def temp_store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = AuditStore(db_path=db_path)
    yield store
    if os.path.exists(db_path):
        os.remove(db_path)


def test_session_lifecycle(temp_store):
    session = SessionRecord(id="sess-001", client_name="Claude Desktop")
    created = temp_store.create_session(session)
    assert created.id == "sess-001"
    assert created.total_actions == 0

    fetched = temp_store.get_session_by_id("sess-001")
    assert fetched is not None
    assert fetched.client_name == "Claude Desktop"

    fetched.ended_at = datetime.now(timezone.utc)
    fetched.summary = "Ran 2 safe commands."
    updated = temp_store.update_session(fetched)
    assert updated.summary == "Ran 2 safe commands."


def test_action_logging_and_export(temp_store):
    session = SessionRecord(id="sess-002", client_name="Antigravity")
    temp_store.create_session(session)

    log_entry = ActionLog(
        id="act-001",
        session_id="sess-002",
        tool_name="bash",
        raw_payload='{"command": "ls -la"}',
        plain_language_explanation="Lists directory contents.",
        language_code="en",
        risk_score=15,
        risk_factors="[]",
        status="AUTO_APPROVED",
        user_decision_by="AUTO_POLICY",
    )
    temp_store.log_action(log_entry)

    # Check that session total_actions updated
    sess = temp_store.get_session_by_id("sess-002")
    assert sess.total_actions == 1
    assert sess.blocked_actions == 0

    # Retrieve action
    act = temp_store.get_action("act-001")
    assert act is not None
    assert act.tool_name == "bash"

    # Export logs
    exported = temp_store.export_logs("sess-002")
    assert len(exported) == 1
    assert exported[0]["id"] == "act-001"
    assert exported[0]["plain_language_explanation"] == "Lists directory contents."


def test_policy_rules_crud(temp_store):
    rule = PolicyRule(
        id="rule-001",
        rule_type="DENY_PATH",
        pattern=".env*",
        description="Block access to env files",
    )
    temp_store.add_policy_rule(rule)

    rules = temp_store.get_policy_rules()
    assert len(rules) == 1
    assert rules[0].pattern == ".env*"

    rule.is_active = False
    temp_store.update_policy_rule(rule)
    active_rules = temp_store.get_policy_rules(active_only=True)
    assert len(active_rules) == 0

    deleted = temp_store.delete_policy_rule("rule-001")
    assert deleted is True
    assert len(temp_store.get_policy_rules(active_only=False)) == 0


def test_system_config_defaults():
    cfg = SystemConfig()
    assert cfg.approval_threshold == 50
    assert cfg.active_language == "auto"
    assert cfg.explainer_mode == "plain"
    assert cfg.dlp_enabled is True


def test_prune_low_disk_preserves_high_risk(temp_store):
    # Req 6.4: Prunes oldest low-risk logs while strictly preserving high-risk and blocked entries
    session = SessionRecord(id="sess-prune", client_name="Test")
    temp_store.create_session(session)

    # 1. Low risk auto-approved (should be pruned)
    low_risk = ActionLog(
        id="act-low",
        session_id="sess-prune",
        tool_name="bash",
        raw_payload='{"cmd": "ls"}',
        plain_language_explanation="Lists files.",
        language_code="en",
        risk_score=10,
        risk_factors="[]",
        status="AUTO_APPROVED",
        user_decision_by="AUTO_POLICY",
    )
    temp_store.log_action(low_risk)

    # 2. High risk action (MUST be preserved)
    high_risk = ActionLog(
        id="act-high",
        session_id="sess-prune",
        tool_name="bash",
        raw_payload='{"cmd": "rm -rf /"}',
        plain_language_explanation="Destructive delete.",
        language_code="en",
        risk_score=95,
        risk_factors='["destructive"]',
        status="REJECTED",
        user_decision_by="AUTO_POLICY",
    )
    temp_store.log_action(high_risk)

    # 3. User manual approval action (MUST be preserved)
    manual_approved = ActionLog(
        id="act-manual",
        session_id="sess-prune",
        tool_name="bash",
        raw_payload='{"cmd": "git push"}',
        plain_language_explanation="Push to git.",
        language_code="en",
        risk_score=60,
        risk_factors="[]",
        status="APPROVED",
        user_decision_by="USER_MANUAL",
    )
    temp_store.log_action(manual_approved)

    # Run prune with force=True
    deleted = temp_store.prune_if_disk_low(force=True, threshold_score=50)
    assert deleted == 1

    # Verify low-risk was purged
    assert temp_store.get_action("act-low") is None

    # Verify high-risk and manual decisions are strictly preserved
    assert temp_store.get_action("act-high") is not None
    assert temp_store.get_action("act-manual") is not None


def test_legacy_session_backfill_and_title(temp_store):
    legacy = SessionRecord(id="legacy-001", client_name="AI Client")
    temp_store.create_session(legacy)

    sessions = temp_store.list_sessions()
    target = next((s for s in sessions if s.id == "legacy-001"), None)
    assert target is not None
    assert target.client_name == "VS Code + GitHub Copilot"
    assert "Connected" in target.title

