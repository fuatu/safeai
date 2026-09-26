"""Tests for AI client configuration generators."""

import tempfile
import json
from pathlib import Path
from scripts.generate_configs import (
    get_claude_desktop_config,
    get_copilot_config,
    get_antigravity_config,
    get_cursor_config,
    get_windsurf_config,
    export_client_configs,
)


def test_get_claude_desktop_config():
    cfg = get_claude_desktop_config(port=9090)
    assert "mcpServers" in cfg
    assert "safeai" in cfg["mcpServers"]
    assert "http://localhost:9090/mcp?client_name=ClaudeDesktop" in cfg["mcpServers"]["safeai"]["args"]


def test_get_copilot_config():
    cfg = get_copilot_config(port=8080)
    assert "mcpServers" in cfg
    assert "safeai" in cfg["mcpServers"]
    assert cfg["mcpServers"]["safeai"]["type"] == "sse"
    assert cfg["mcpServers"]["safeai"]["url"] == "http://localhost:8080/mcp?client_name=GithubCopilot"


def test_get_antigravity_config():
    cfg = get_antigravity_config(port=8080)
    assert cfg["mcpServers"]["safeai"]["type"] == "sse"
    assert cfg["mcpServers"]["safeai"]["url"] == "http://localhost:8080/mcp?client_name=antigravity"


def test_get_cursor_config():
    cfg = get_cursor_config(port=8080)
    assert cfg["mcp"]["servers"][0]["url"] == "http://localhost:8080/mcp?client_name=Cursor"
    assert cfg["openai_proxy"]["base_url"] == "http://localhost:8080/v1"


def test_get_windsurf_config():
    cfg = get_windsurf_config(port=8080)
    assert "mcpServers" in cfg
    assert "safeai" in cfg["mcpServers"]
    assert cfg["mcpServers"]["safeai"]["serverUrl"] == "http://localhost:8080/mcp?client_name=Windsurf"


def test_export_client_configs():
    with tempfile.TemporaryDirectory() as tmp_dir:
        export_client_configs(output_dir=tmp_dir, port=8080)
        p = Path(tmp_dir)
        assert (p / "claude_desktop_config.json").exists()
        assert (p / "copilot_mcp_config.json").exists()
        assert (p / "antigravity_mcp_config.json").exists()
        assert (p / "cursor_config.json").exists()
        assert (p / "windsurf_mcp_config.json").exists()
        assert (p / "copilot_instructions.md").exists()
        assert (p / "antigravity_safeai_policy.md").exists()
        assert (p / "cursorrules").exists()
        assert (p / "windsurfrules").exists()

        # Validate JSON content
        with open(p / "copilot_mcp_config.json") as f:
            data = json.load(f)
            assert "safeai" in data["mcpServers"]

        # Validate rule content
        with open(p / "antigravity_safeai_policy.md") as f:
            rule_text = f.read()
            assert "run_command" in rule_text
            assert "SafeAI Governance & Execution Policy" in rule_text
