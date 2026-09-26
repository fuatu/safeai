"""Tests for AI client configuration generators."""

import tempfile
import json
from pathlib import Path
from scripts.generate_configs import (
    get_claude_desktop_config,
    get_copilot_config,
    get_antigravity_config,
    get_cursor_config,
    export_client_configs,
)


def test_get_claude_desktop_config():
    cfg = get_claude_desktop_config(port=9090)
    assert "mcpServers" in cfg
    assert "safeai" in cfg["mcpServers"]
    assert "http://localhost:9090/mcp" in cfg["mcpServers"]["safeai"]["args"]


def test_get_copilot_config():
    cfg = get_copilot_config(port=8080)
    assert "mcpServers" in cfg
    assert "safeai" in cfg["mcpServers"]
    assert cfg["mcpServers"]["safeai"]["type"] == "sse"
    assert cfg["mcpServers"]["safeai"]["url"] == "http://localhost:8080/mcp"


def test_get_antigravity_config():
    cfg = get_antigravity_config(port=8080)
    assert cfg["mcpServers"]["safeai"]["type"] == "sse"
    assert cfg["mcpServers"]["safeai"]["url"] == "http://localhost:8080/mcp"


def test_get_cursor_config():
    cfg = get_cursor_config(port=8080)
    assert cfg["mcp"]["servers"][0]["url"] == "http://localhost:8080/mcp"
    assert cfg["openai_proxy"]["base_url"] == "http://localhost:8080/v1"


def test_export_client_configs():
    with tempfile.TemporaryDirectory() as tmp_dir:
        export_client_configs(output_dir=tmp_dir, port=8080)
        p = Path(tmp_dir)
        assert (p / "claude_desktop_config.json").exists()
        assert (p / "copilot_mcp_config.json").exists()
        assert (p / "antigravity_mcp_config.json").exists()
        assert (p / "cursor_config.json").exists()

        # Validate JSON content
        with open(p / "copilot_mcp_config.json") as f:
            data = json.load(f)
            assert "safeai" in data["mcpServers"]
