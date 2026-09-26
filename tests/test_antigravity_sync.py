"""Tests for AntigravityChatSyncer automated tool invocation and session ingestion."""

import json
import os
import tempfile
from pathlib import Path
import pytest

from backend.storage.audit_store import AuditStore
from backend.storage.antigravity_sync import AntigravityChatSyncer


@pytest.fixture
def antigravity_test_env():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_safeai.db")
        store = AuditStore(db_path=db_path)

        # Create mock Antigravity brain directory structure
        brain_dir = Path(tmpdir) / "brain" / "conv-test-1234" / ".system_generated" / "logs"
        brain_dir.mkdir(parents=True)

        yield store, brain_dir


def test_antigravity_session_tracking_without_chat_turns(antigravity_test_env):
    store, brain_dir = antigravity_test_env

    transcript_file = brain_dir / "transcript.jsonl"
    lines = [
        {
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "<USER_REQUEST>\nHow do I secure this database?\n</USER_REQUEST>\n<ADDITIONAL_METADATA>",
            "created_at": "2026-09-26T12:00:00Z",
        },
        {
            "step_index": 1,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": "Enable SSL/TLS and use strong password policies.",
            "tool_calls": [],
            "created_at": "2026-09-26T12:00:05Z",
        },
    ]

    with open(transcript_file, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    syncer = AntigravityChatSyncer(
        audit_store=store,
        custom_storage_dir=str(brain_dir.parent.parent.parent),
    )

    # 0 tool invocations -> 0 actions logged
    synced = syncer.sync_latest()
    assert synced == 0

    actions = store.list_actions(limit=10)
    assert len(actions) == 0

    # Session history is still created and tracked
    sessions = store.list_sessions(limit=5)
    assert len(sessions) == 1
    assert "Google Antigravity IDE" in sessions[0].client_name
    assert "How do I secure this database?" in sessions[0].title


def test_antigravity_tool_calls_syncing(antigravity_test_env):
    store, brain_dir = antigravity_test_env
    transcript_file = brain_dir / "transcript.jsonl"
    lines = [
        {
            "step_index": 0,
            "source": "USER_EXPLICIT",
            "type": "USER_INPUT",
            "content": "<USER_REQUEST>\nList all users in AWS\n</USER_REQUEST>",
            "created_at": "2026-09-26T12:00:00Z",
        },
        {
            "step_index": 1,
            "source": "MODEL",
            "type": "PLANNER_RESPONSE",
            "content": "Running AWS CLI check...",
            "tool_calls": [
                {
                    "name": "run_command",
                    "args": {
                        "CommandLine": '"export AWS_PAGER=\\"\\" && aws iam list-users --max-items 10"',
                        "Cwd": '"/workspace"',
                    },
                }
            ],
            "created_at": "2026-09-26T12:00:02Z",
        },
        {
            "step_index": 2,
            "source": "MODEL",
            "type": "RUN_COMMAND",
            "content": '{"Users": [{"UserName": "admin"}]}',
            "created_at": "2026-09-26T12:00:04Z",
        },
    ]

    with open(transcript_file, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l) + "\n")

    syncer = AntigravityChatSyncer(
        audit_store=store,
        custom_storage_dir=str(brain_dir.parent.parent.parent),
    )

    synced = syncer.sync_latest()
    # Only 1 tool invocation is synced (no chat turn)
    assert synced == 1

    actions = store.list_actions(limit=10)
    assert len(actions) == 1

    cmd_action = actions[0]
    assert cmd_action.tool_name == "bash"
    assert "aws iam list-users" in cmd_action.raw_payload
    assert cmd_action.risk_score == 35
    assert "cloud_iam_enumeration" in cmd_action.risk_factors
    assert "admin" in cmd_action.execution_result
    assert "Antigravity" in cmd_action.plain_language_explanation

    # Verify duplicate prevention
    assert syncer.sync_latest() == 0
    assert len(store.list_actions(limit=10)) == 1
