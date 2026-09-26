"""Tests for OpenAI /v1/chat/completions proxy interception."""

import asyncio
import os
import tempfile
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.explainer.engine import ExplainerEngine
from backend.gateway.openai_proxy import OpenAIProxyRouter
from backend.hitl.broker import HITLBroker
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


@pytest.fixture
def openai_test_app():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = AuditStore(db_path=db_path)
    sec_engine = SecurityEngine()
    explainer = ExplainerEngine()
    hitl_broker = HITLBroker(approval_threshold=50)
    dlp = DLPMasker()

    proxy_router = OpenAIProxyRouter(
        security_engine=sec_engine,
        explainer_engine=explainer,
        hitl_broker=hitl_broker,
        dlp_masker=dlp,
        audit_store=store,
    )

    app = FastAPI()
    app.include_router(proxy_router.router)

    yield app, store, hitl_broker
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_openai_proxy_safe_tool_call(openai_test_app):
    app, store, _ = openai_test_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_body = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "echo hello"}',
                            },
                        }
                    ],
                }
            ],
            "user": "session-oai-1",
        }
        resp = await client.post("/v1/chat/completions", json=req_body)
        assert resp.status_code == 200
        data = resp.json()
        assert "choices" in data

    # Verify action was recorded in AuditStore
    actions = store.list_actions("session-oai-1")
    assert len(actions) == 1
    assert actions[0].status == "AUTO_APPROVED"


@pytest.mark.asyncio
async def test_openai_proxy_high_risk_rejection(openai_test_app):
    app, store, hitl_broker = openai_test_app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        req_body = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_2",
                            "type": "function",
                            "function": {
                                "name": "bash",
                                "arguments": '{"command": "rm -rf /System"}',
                            },
                        }
                    ],
                }
            ],
            "user": "session-oai-2",
        }

        async def deny_pending():
            await asyncio.sleep(0.05)
            pending = hitl_broker.get_pending_approvals()
            assert len(pending) == 1
            await hitl_broker.submit_decision(pending[0]["actionId"], "DENY")

        client_task = asyncio.create_task(client.post("/v1/chat/completions", json=req_body))
        deny_task = asyncio.create_task(deny_pending())

        resp, _ = await asyncio.gather(client_task, deny_task)
        assert resp.status_code == 403
        data = resp.json()
        assert "Policy Denial" in data["error"]["message"]
