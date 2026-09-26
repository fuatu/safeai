"""Tests for POST /api/eval/intercept pre-execution gate and connection holding."""

import asyncio
import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app


@pytest.fixture
def test_app():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path=db_path)
    yield app
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_intercept_safe_command(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post(
            "/api/eval/intercept",
            json={"command": "git status", "client_name": "Test CLI"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["decision"] == "ALLOW"
        assert data["risk_score"] == 0
        assert "git" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_intercept_database_data_loss_held_and_approved(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Start interception of risky database deletion in background task
        intercept_task = asyncio.create_task(
            client.post(
                "/api/eval/intercept",
                json={
                    "command": "sqlite3 ./data/safeai.db \"DELETE FROM sessions;\"",
                    "client_name": "Test Shell Gate",
                    "timeout_seconds": 5,
                },
            )
        )

        # Allow loop to process and hit HITL wait
        await asyncio.sleep(0.05)

        # Verify pending approval appeared in broker
        pending_resp = await client.get("/api/approvals/pending")
        assert pending_resp.status_code == 200
        pending = pending_resp.json()
        assert len(pending) == 1
        action_id = pending[0]["actionId"]
        assert pending[0]["riskScore"] >= 70
        assert any("sql_" in f for f in pending[0]["riskFactors"])

        # Human supervisor approves the action
        decide_resp = await client.post(
            "/api/approvals/decide",
            json={"actionId": action_id, "decision": "APPROVE", "notes": "Approved for fresh test run"},
        )
        assert decide_resp.status_code == 200

        # Wait for intercept task to complete
        res = await intercept_task
        assert res.status_code == 200
        result_data = res.json()
        assert result_data["decision"] == "ALLOW"
        assert result_data["user_decision_by"] == "USER_MANUAL"
        assert result_data["notes"] == "Approved for fresh test run"


@pytest.mark.asyncio
async def test_intercept_critical_file_delete_denied(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Start interception of dangerous file delete
        intercept_task = asyncio.create_task(
            client.post(
                "/api/eval/intercept",
                json={
                    "command": "rm -f ./data/safeai.db",
                    "client_name": "Test Shell Gate",
                    "timeout_seconds": 5,
                },
            )
        )

        await asyncio.sleep(0.05)

        pending_resp = await client.get("/api/approvals/pending")
        pending = pending_resp.json()
        assert len(pending) == 1
        action_id = pending[0]["actionId"]
        assert pending[0]["riskScore"] >= 70

        # Human supervisor denies the action
        decide_resp = await client.post(
            "/api/approvals/decide",
            json={"actionId": action_id, "decision": "DENY", "notes": "Prevent accidental database deletion"},
        )
        assert decide_resp.status_code == 200

        res = await intercept_task
        assert res.status_code == 200
        result_data = res.json()
        assert result_data["decision"] == "BLOCK"
        assert "Prevent accidental database deletion" in result_data["reason"]


@pytest.mark.asyncio
async def test_intercept_cloud_destruction_held(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        intercept_task = asyncio.create_task(
            client.post(
                "/api/eval/intercept",
                json={
                    "command": "aws ec2 terminate-instances --instance-ids i-99999",
                    "client_name": "Cloud CLI",
                    "timeout_seconds": 5,
                },
            )
        )

        await asyncio.sleep(0.05)

        pending_resp = await client.get("/api/approvals/pending")
        pending = pending_resp.json()
        assert len(pending) == 1
        assert pending[0]["riskScore"] >= 85
        assert any("aws_ec2_terminate" in f for f in pending[0]["riskFactors"])

        # Deny
        await client.post(
            "/api/approvals/decide",
            json={"actionId": pending[0]["actionId"], "decision": "DENY"},
        )
        res = await intercept_task
        assert res.json()["decision"] == "BLOCK"
