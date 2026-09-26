#!/usr/bin/env python3
"""
Generates one-click configuration snippets for AI clients
(Claude Desktop, Google Antigravity, Cursor, Windsurf, Codex)
to connect seamlessly through SafeAI's transparent governance gateway.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any


def get_claude_desktop_config(port: int = 8080) -> Dict[str, Any]:
    """Generates configuration for Anthropic Claude Desktop."""
    return {
        "mcpServers": {
          "safeai": {
            "command": "npx",
            "args": ["-y", "mcp-remote", f"http://localhost:{port}/mcp"]
          }
        }
    }


def get_antigravity_config(port: int = 8080) -> Dict[str, Any]:
    """Generates configuration for Google Antigravity IDE (mcp_config.json)."""
    return {
        "mcpServers": {
            "safeai": {
                "type": "sse",
                "url": f"http://localhost:{port}/mcp",
                "description": "SafeAI Local Governance Gateway & Plain-Language Explainer"
            }
        }
    }


def get_cursor_config(port: int = 8080) -> Dict[str, Any]:
    """Generates configuration for Cursor IDE (MCP & OpenAI Proxy)."""
    return {
        "mcp": {
            "servers": [
                {
                    "name": "safeai",
                    "type": "sse",
                    "url": f"http://localhost:{port}/mcp"
                }
            ]
        },
        "openai_proxy": {
            "base_url": f"http://localhost:{port}/v1",
            "api_key": "safeai-local-key"
        }
    }


def export_client_configs(output_dir: str = "./client_configs", port: int = 8080) -> None:
    """Exports generated client JSON files to output directory."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Claude Desktop
    claude_file = out_path / "claude_desktop_config.json"
    with open(claude_file, "w", encoding="utf-8") as f:
        json.dump(get_claude_desktop_config(port), f, indent=2)

    # 2. Antigravity IDE
    antigravity_file = out_path / "antigravity_mcp_config.json"
    with open(antigravity_file, "w", encoding="utf-8") as f:
        json.dump(get_antigravity_config(port), f, indent=2)

    # 3. Cursor IDE
    cursor_file = out_path / "cursor_config.json"
    with open(cursor_file, "w", encoding="utf-8") as f:
        json.dump(get_cursor_config(port), f, indent=2)

    print(f"Generated AI client configurations in: {out_path.resolve()}")
    print(f" - Claude Desktop: {claude_file.name}")
    print(f" - Antigravity:    {antigravity_file.name}")
    print(f" - Cursor:         {cursor_file.name}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate AI client configs for SafeAI")
    parser.add_argument("--port", type=int, default=8080, help="SafeAI gateway port (default: 8080)")
    parser.add_argument("--out", type=str, default="./client_configs", help="Output directory")
    args = parser.parse_args()

    export_client_configs(output_dir=args.out, port=args.port)
