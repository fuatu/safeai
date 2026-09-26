"""AI Client configuration generator and metadata provider."""

from typing import Any, Dict


def get_claude_desktop_config(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Generates configuration for Anthropic Claude Desktop."""
    return {
        "mcpServers": {
            "safeai": {
                "command": "npx",
                "args": ["-y", "mcp-remote", f"http://{host}:{port}/mcp?client_name=ClaudeDesktop"],
            }
        }
    }


def get_antigravity_config(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Generates configuration for Google Antigravity IDE (mcp_config.json)."""
    return {
        "mcpServers": {
            "safeai": {
                "type": "sse",
                "url": f"http://{host}:{port}/mcp?client_name=antigravity",
                "description": "SafeAI Local Governance Gateway & Plain-Language Explainer",
            }
        }
    }


def get_cursor_config(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Generates configuration for Cursor IDE (MCP & OpenAI Proxy)."""
    return {
        "mcp": {
            "servers": [
                {
                    "name": "safeai",
                    "type": "sse",
                    "url": f"http://{host}:{port}/mcp?client_name=Cursor",
                }
            ]
        },
        "openai_proxy": {
            "base_url": f"http://{host}:{port}/v1",
            "api_key": "safeai-local-key",
        },
    }


def get_copilot_config(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Generates configuration for GitHub Copilot in VS Code (.vscode/mcp.json)."""
    return {
        "mcpServers": {
            "safeai": {
                "type": "sse",
                "url": f"http://{host}:{port}/mcp?client_name=GithubCopilot",
                "description": "SafeAI Agent Guard & Explainer for GitHub Copilot",
            }
        }
    }


def get_all_client_configs(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Returns comprehensive client connection metadata, files, and guides."""
    return {
        "claude": {
            "id": "claude",
            "name": "Claude Desktop",
            "filename": "claude_desktop_config.json",
            "description": "Connect Anthropic Claude Desktop via transparent MCP remote bridge.",
            "target_paths": {
                "mac": "~/Library/Application Support/Claude/claude_desktop_config.json",
                "windows": "%APPDATA%\\Claude\\claude_desktop_config.json",
                "linux": "~/.config/Claude/claude_desktop_config.json",
            },
            "config": get_claude_desktop_config(port=port, host=host),
            "command_hint": f"npx -y mcp-remote http://{host}:{port}/mcp?client_name=ClaudeDesktop",
        },
        "copilot": {
            "id": "copilot",
            "name": "GitHub Copilot",
            "filename": "mcp.json",
            "description": "Connect GitHub Copilot in VS Code via workspace .vscode/mcp.json or the Add MCP Server wizard.",
            "target_paths": {
                "ui_wizard": "VS Code -> Add MCP Server -> Select 'HTTP (HTTP or Server-Sent Events)'",
                "workspace": ".vscode/mcp.json",
                "user_settings": "VS Code Settings -> Extensions -> GitHub Copilot Chat -> MCP",
            },
            "config": get_copilot_config(port=port, host=host),
            "command_hint": f"Endpoint: http://{host}:{port}/mcp?client_name=GithubCopilot",
        },
        "antigravity": {
            "id": "antigravity",
            "name": "Google Antigravity IDE",
            "filename": "mcp_config.json",
            "description": "Native Server-Sent Events (SSE) integration for Antigravity pair programming.",
            "target_paths": {
                "workspace": ".agents/mcp_config.json",
                "global": "~/.gemini/antigravity-ide/mcp_config.json",
            },
            "config": get_antigravity_config(port=port, host=host),
            "command_hint": f"Endpoint: http://{host}:{port}/mcp?client_name=antigravity",
        },
        "cursor": {
            "id": "cursor",
            "name": "Cursor / Windsurf",
            "filename": "cursor_config.json",
            "description": "MCP SSE server connection and OpenAI-compatible LLM proxy.",
            "target_paths": {
                "cursor_settings": "Cursor Settings -> Features -> MCP -> Add New MCP Server",
                "windsurf_settings": "Windsurf Settings -> Cascade -> MCP Plugins",
            },
            "config": get_cursor_config(port=port, host=host),
            "command_hint": f"SSE: http://{host}:{port}/mcp?client_name=Cursor | Base URL: http://{host}:{port}/v1",
        },
        "generic": {
            "id": "generic",
            "name": "Generic MCP & OpenAI Proxy",
            "filename": "safeai_connection.json",
            "description": "Universal connection details for custom autonomous agents and tools.",
            "mcp_url": f"http://{host}:{port}/mcp?client_name=CustomAgent",
            "openai_base_url": f"http://{host}:{port}/v1",
            "api_key": "safeai-local-key",
            "config": {
                "mcp_endpoint": f"http://{host}:{port}/mcp?client_name=CustomAgent",
                "openai_endpoint": f"http://{host}:{port}/v1",
                "auth_header": "Bearer safeai-local-key",
            },
            "command_hint": f"curl -X POST http://{host}:{port}/mcp?client_name=CustomAgent",
        },
    }
