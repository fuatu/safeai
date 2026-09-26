"""Tests for GatewayProxy MCP JSON-RPC interception and execution."""

import asyncio
import tempfile
import os
import pytest

from backend.explainer.engine import ExplainerEngine
from backend.gateway.proxy import GatewayProxy
from backend.hitl.broker import HITLBroker
from backend.models.schemas import SessionRecord
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


@pytest.fixture
def proxy_env():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = AuditStore(db_path=db_path)
    sec_engine = SecurityEngine()
    explainer = ExplainerEngine()
    hitl_broker = HITLBroker(approval_threshold=50)
    dlp = DLPMasker()

    proxy = GatewayProxy(
        security_engine=sec_engine,
        explainer_engine=explainer,
        hitl_broker=hitl_broker,
        dlp_masker=dlp,
        audit_store=store,
    )
    yield proxy, store, hitl_broker
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_mcp_initialize(proxy_env):
    proxy, _, _ = proxy_env
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }
    resp = await proxy.handle_mcp_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "capabilities" in resp["result"]
    assert resp["result"]["serverInfo"]["name"] == "safeai-governance-gateway"


@pytest.mark.asyncio
async def test_mcp_tools_list(proxy_env):
    proxy, _, _ = proxy_env
    req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
    resp = await proxy.handle_mcp_request(req, active_language="en")
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "bash" in tool_names


@pytest.mark.asyncio
async def test_mcp_tool_call_auto_approved(proxy_env):
    # Safe command -> auto-approved, executes echo, outputs redacted result
    proxy, store, _ = proxy_env
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "bash",
            "arguments": {"command": "echo 'Hello SafeAI'"},
        },
    }
    resp = await proxy.handle_mcp_request(req, session_id="test-session")
    assert "result" in resp
    content_text = resp["result"]["content"][0]["text"]
    assert "Hello SafeAI" in content_text

    # Verify audit store logged the action
    actions = store.list_actions("test-session")
    assert len(actions) == 1
    assert actions[0].status == "AUTO_APPROVED"
    assert "Hello SafeAI" in actions[0].execution_result


@pytest.mark.asyncio
async def test_mcp_tool_call_high_risk_rejection(proxy_env):
    # Destructive command -> suspended, then denied
    proxy, store, hitl_broker = proxy_env
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "bash",
            "arguments": {"command": "rm -rf /test_dir"},
        },
    }

    async def deny_pending():
        await asyncio.sleep(0.05)
        pending = hitl_broker.get_pending_approvals()
        assert len(pending) == 1
        await hitl_broker.submit_decision(pending[0]["actionId"], "DENY")

    proxy_task = asyncio.create_task(proxy.handle_mcp_request(req, session_id="test-session"))
    deny_task = asyncio.create_task(deny_pending())

    resp, _ = await asyncio.gather(proxy_task, deny_task)
    assert "error" in resp
    assert resp["error"]["code"] == -32000
    assert "Security Policy Denial" in resp["error"]["message"]


@pytest.mark.asyncio
async def test_mcp_tool_call_dlp_masking(proxy_env):
    # Command containing secret -> secret redacted before log & execution
    proxy, store, _ = proxy_env
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "bash",
            "arguments": {"command": "echo 'Deploying with AKIAIOSFODNN7EXAMPLE'"},
        },
    }
    resp = await proxy.handle_mcp_request(req, session_id="dlp-session")
    content_text = resp["result"]["content"][0]["text"]
    assert "AKIAIOSFODNN7EXAMPLE" not in content_text
    assert "[REDACTED_AWS_KEY]" in content_text

    # Check database action log
    actions = store.list_actions("dlp-session")
    assert "AKIAIOSFODNN7EXAMPLE" not in actions[0].raw_payload
    assert "[REDACTED_AWS_KEY]" in actions[0].raw_payload
