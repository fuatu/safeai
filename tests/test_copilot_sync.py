"""Tests for CopilotChatSyncer automated VS Code chat history ingestion."""

import json
import os
import tempfile
from pathlib import Path
import pytest

from backend.models.schemas import SessionRecord
from backend.storage.audit_store import AuditStore
from backend.storage.copilot_sync import CopilotChatSyncer


@pytest.fixture
def copilot_test_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_safeai.db")
        store = AuditStore(db_path=db_path)

        # Create mock workspaceStorage directory structure
        ws_dir = Path(tmpdir) / "workspaceStorage" / "test-workspace-hash" / "chatSessions"
        ws_dir.mkdir(parents=True)

        yield store, ws_dir


def test_copilot_chat_syncer(copilot_test_env):
    store, ws_dir = copilot_test_env

    # Write a mock chatSession jsonl file mimicking VS Code
    chat_file = ws_dir / "session-001.jsonl"
    lines = [
        {"kind": 0, "v": {"sessionId": "session-001", "model": "copilot/gemini-3.8-flash"}},
        {
            "kind": 2,
            "k": ["requests"],
            "v": [
                {
                    "requestId": "req_1",
                    "timestamp": 1790420760000,
                    "modelId": "copilot/gemini-3.8-flash",
                    "message": {"text": "How do I secure this database?"},
                }
            ],
        },
        {
            "kind": 2,
            "k": ["requests", 0, "response"],
            "v": [{"value": "Use strong passwords and enable TLS encryption."}],
        },
    ]

    with open(chat_file, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    syncer = CopilotChatSyncer(
        audit_store=store,
        custom_storage_dir=str(ws_dir.parent.parent),
    )

    # Run sync
    synced = syncer.sync_latest()
    assert synced == 1

    # Verify action was logged
    actions = store.list_actions(limit=10)
    assert len(actions) == 1
    action = actions[0]
    assert action.tool_name == "copilot_chat"
    assert "How do I secure this database?" in action.plain_language_explanation
    assert "TLS encryption" in action.execution_result
    assert action.risk_score == 5
    assert action.status == "AUTO_APPROVED"

    # Verify second sync does not duplicate
    synced_again = syncer.sync_latest()
    assert synced_again == 0
    assert len(store.list_actions(limit=10)) == 1
