"""Tests for REST API routes and WebSockets dispatcher."""

import asyncio
import json
import os
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.models.schemas import PolicyRule, SessionRecord


@pytest.fixture
def app_instance():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    app = create_app(db_path=db_path)
    yield app
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_health_check(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["gateway"] == "SafeAI Core"


@pytest.mark.asyncio
async def test_settings_hot_reload(app_instance):
    # Req 5.4: Modifying policy settings applies to subsequent calls without restart
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Check defaults
        get_res = await client.get("/api/settings")
        assert get_res.status_code == 200
        assert get_res.json()["approval_threshold"] == 50

        # Update threshold and language
        put_res = await client.put(
            "/api/settings",
            json={"approval_threshold": 65, "active_language": "tr"},
        )
        assert put_res.status_code == 200
        updated = put_res.json()
        assert updated["approval_threshold"] == 65
        assert updated["active_language"] == "tr"

        # Verify persisted in memory
        get_res2 = await client.get("/api/settings")
        assert get_res2.json()["approval_threshold"] == 65
        assert get_res2.json()["active_language"] == "tr"


@pytest.mark.asyncio
async def test_policy_rules_api_crud(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Create
        new_rule = {
            "id": "rule-api-1",
            "rule_type": "DENY_COMMAND",
            "pattern": "mkfs.*",
            "description": "Prevent disk format",
            "is_active": True,
        }
        post_res = await client.post("/api/policy/rules", json=new_rule)
        assert post_res.status_code == 200

        # List
        list_res = await client.get("/api/policy/rules")
        assert list_res.status_code == 200
        rules = list_res.json()
        assert any(r["id"] == "rule-api-1" for r in rules)

        # Delete
        del_res = await client.delete("/api/policy/rules/rule-api-1")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_approvals_api_workflow(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Trigger an MCP tool call that requires approval (rm -rf)
        req_mcp = {
            "jsonrpc": "2.0",
            "id": "test-req",
            "method": "tools/call",
            "params": {"name": "bash", "arguments": {"command": "rm -rf /test_api"}},
        }

        async def decide_via_api():
            await asyncio.sleep(0.05)
            # Fetch pending
            pend_res = await client.get("/api/approvals/pending")
            assert pend_res.status_code == 200
            items = pend_res.json()
            assert len(items) == 1
            act_id = items[0]["actionId"]

            # Submit approve
            dec_res = await client.post(
                "/api/approvals/decide",
                json={"actionId": act_id, "decision": "APPROVE", "notes": "Approved via REST"},
            )
            assert dec_res.status_code == 200

        mcp_task = asyncio.create_task(client.post("/mcp", json=req_mcp))
        decide_task = asyncio.create_task(decide_via_api())

        mcp_res, _ = await asyncio.gather(mcp_task, decide_task)
        assert mcp_res.status_code == 200
        assert "result" in mcp_res.json()


@pytest.mark.asyncio
async def test_tool_settings_api_crud(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Upsert tool setting
        setting = {
            "tool_name": "git_push",
            "custom_threshold": 40,
            "bypass_approval": False,
            "timeout_ms": 20000,
            "is_enabled": True,
            "description": "Git push tool",
        }
        post_res = await client.post("/api/tools/settings", json=setting)
        assert post_res.status_code == 200
        assert post_res.json()["tool_name"] == "git_push"

        # List tool settings
        list_res = await client.get("/api/tools/settings")
        assert list_res.status_code == 200
        settings = list_res.json()
        assert any(s["tool_name"] == "git_push" for s in settings)

        # Get specific tool setting
        get_res = await client.get("/api/tools/settings/git_push")
        assert get_res.status_code == 200
        assert get_res.json()["custom_threshold"] == 40

        # Delete tool setting
        del_res = await client.delete("/api/tools/settings/git_push")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"


@pytest.mark.asyncio
async def test_client_configs_api(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        res = await client.get("/api/client-configs?port=8080")
        assert res.status_code == 200
        data = res.json()
        assert "claude" in data
        assert "copilot" in data
        assert "antigravity" in data
        assert "cursor" in data
        assert "windsurf" in data
        assert "generic" in data
        assert data["claude"]["filename"] == "claude_desktop_config.json"
        assert data["copilot"]["filename"] == "mcp.json"
        assert "safeai" in data["claude"]["config"]["mcpServers"]
        assert "safeai" in data["copilot"]["config"]["mcpServers"]
        assert "enforcement_rule" in data["copilot"]
        assert "enforcement_rule" in data["antigravity"]
        assert "enforcement_rule" in data["cursor"]
        assert "enforcement_rule" in data["windsurf"]


@pytest.mark.asyncio
async def test_list_actions_all_sessions(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        res = await client.get("/api/actions?limit=50")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_clean_database_api(app_instance):
    async with AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test") as client:
        # Add a test policy rule
        await client.post(
            "/api/policy/rules",
            json={"id": "rule-clean-test", "rule_type": "DENY_PATH", "pattern": "/tmp/*"},
        )
        # Call clean database endpoint
        clean_res = await client.post(
            "/api/database/clean",
            json={"keep_policy_rules": True, "keep_tool_settings": True},
        )
        assert clean_res.status_code == 200
        data = clean_res.json()
        assert data["status"] == "success"
        assert "actions_deleted" in data
        assert "sessions_deleted" in data

        # Check policy rule is preserved
        rules_res = await client.get("/api/policy/rules")
        assert any(r["id"] == "rule-clean-test" for r in rules_res.json())



