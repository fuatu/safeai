"""Tests for CopilotChatSyncer automated VS Code tool invocation and session ingestion."""

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


def test_copilot_session_tracking_without_chat_turns(copilot_test_env):
    store, ws_dir = copilot_test_env

    # Write a mock chatSession jsonl file with only conversational text
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

    # Run sync: no tool invocations, so 0 actions
    synced = syncer.sync_latest()
    assert synced == 0

    # Verify no conversational turns are logged as actions
    actions = store.list_actions(limit=10)
    assert len(actions) == 0

    # Verify session record is still created and tracked
    sessions = store.list_sessions(limit=10)
    assert len(sessions) == 1
    assert "VS Code + GitHub Copilot" in sessions[0].client_name
    assert "How do I secure this database?" in sessions[0].title


def test_copilot_terminal_tool_syncing(copilot_test_env):
    store, ws_dir = copilot_test_env
    chat_file = ws_dir / "session-002.jsonl"
    lines = [
        {"kind": 0, "v": {"sessionId": "session-002", "model": "copilot/gemini-3.8-flash"}},
        {
            "kind": 2,
            "k": ["requests"],
            "v": [
                {
                    "requestId": "req_2",
                    "timestamp": 1790424421000,
                    "modelId": "copilot/gemini-3.8-flash",
                    "message": {"text": "check if aws cli works and get user list"},
                }
            ],
        },
        {
            "kind": 1,
            "k": ["requests", 0, "result"],
            "v": {
                "metadata": {
                    "toolCallRounds": [
                        {
                            "response": "Here is the list of users.",
                            "toolCalls": [
                                {
                                    "id": "call_test_term_1",
                                    "name": "run_in_terminal",
                                    "arguments": json.dumps({
                                        "command": "export AWS_PAGER=\"\" && aws iam list-users --max-items 10",
                                        "explanation": "List IAM users",
                                    }),
                                }
                            ],
                        }
                    ],
                    "toolCallResults": {
                        "call_test_term_1": {
                            "content": [{"value": '{"Users": [{"UserName": "admin"}]}'}]
                        }
                    },
                }
            },
        },
    ]

    with open(chat_file, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    syncer = CopilotChatSyncer(
        audit_store=store,
        custom_storage_dir=str(ws_dir.parent.parent),
    )

    synced = syncer.sync_latest()
    # Only 1 tool invocation is synced (no chat turn)
    assert synced == 1

    actions = store.list_actions(limit=10)
    assert len(actions) == 1

    # Check terminal tool action
    term_action = actions[0]
    assert term_action.tool_name == "bash"
    assert "aws iam list-users" in term_action.raw_payload
    assert term_action.risk_score == 35
    assert "cloud_iam_enumeration" in term_action.risk_factors
    assert "admin" in term_action.execution_result
    assert "Terminal" in term_action.plain_language_explanation

    # Verify duplicate prevention
    assert syncer.sync_latest() == 0
    assert len(store.list_actions(limit=10)) == 1
