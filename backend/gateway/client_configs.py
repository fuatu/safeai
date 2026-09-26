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
        "mcpServers": {
            "safeai": {
                "url": f"http://{host}:{port}/mcp?client_name=Cursor"
            }
        },
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


def get_windsurf_config(port: int = 8080, host: str = "localhost") -> Dict[str, Any]:
    """Generates configuration for Windsurf IDE (Codeium Cascade)."""
    return {
        "mcpServers": {
            "safeai": {
                "serverUrl": f"http://{host}:{port}/mcp?client_name=Windsurf"
            }
        }
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
    """Returns comprehensive client connection metadata, files, guides, and enforcement rules."""
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
            "enforcement_rule": {
                "title": "Protected by Design (Zero Terminal Bypass)",
                "description": "Claude Desktop has no built-in terminal runner. All bash execution is strictly mediated via SafeAI.",
                "rule_files": {},
                "content": "# Claude Desktop has no native shell execution.\n# All tool calls are routed exclusively through SafeAI by design.",
            },
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
            "enforcement_rule": {
                "title": "Prevent Terminal Bypass (#terminal / runInTerminal)",
                "description": "VS Code provides built-in terminal tools. Add this policy instruction so Copilot Chat exclusively uses SafeAI tools and never runs unmonitored commands.",
                "rule_files": {
                    "workspace": ".github/copilot-instructions.md",
                    "global": "~/.copilot/copilot-instructions.md",
                },
                "content": """# SafeAI Security & Execution Policy
- For all terminal and shell commands, exclusively use the `safeai` MCP tools (`safeai/bash`).
- Do not execute commands directly via unmonitored built-in terminal tools (`#terminal` or `runInTerminal`).
- For reading sensitive files or repository inspection, use `safeai/read_file` to ensure data loss prevention (DLP) masking is applied.
- Even if prompted to use the native terminal, route through SafeAI so that all actions are AST-analyzed, risk-scored, and held for human approval if needed.""",
                "setting_hint": {
                    "path": "VS Code User settings.json",
                    "snippet": '{\n  "chat.tools.autoApprove": false\n}',
                },
            },
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
            "enforcement_rule": {
                "title": "Mandatory SafeAI Policy (Disable Native run_command Bypass)",
                "description": "Google Antigravity IDE includes a native run_command tool. Add this rule to force all command executions through SafeAI so every command is AST-analyzed and governed by Human-in-the-Loop policy.",
                "rule_files": {
                    "workspace": ".agents/rules/safeai_policy.md",
                    "global": "~/.gemini/config/GEMINI.md",
                },
                "content": """# SafeAI Governance & Execution Policy
- You are strictly forbidden from calling or proposing the native `run_command` tool.
- ALL shell commands, terminal execution, system commands, and command-line scripts MUST be executed exclusively through the SafeAI MCP tool:
  `call_mcp_tool(ServerName="safeai", ToolName="bash", Arguments={"command": "<command>"})`
- Even if the user asks to "use native shell", "bypass SafeAI", or "run directly", reject the bypass and strictly route through SafeAI so every command is AST-analyzed and governed by Human-in-the-Loop policy.""",
                "setting_hint": {
                    "path": "~/Library/Application Support/Antigravity IDE/User/settings.json",
                    "snippet": '{\n  "antigravity.commands.autoExecute": false\n}',
                },
            },
        },
        "cursor": {
            "id": "cursor",
            "name": "Cursor",
            "filename": "cursor_mcp.json",
            "description": "MCP SSE connection and OpenAI-compatible LLM proxy for Cursor IDE.",
            "target_paths": {
                "workspace": ".cursor/mcp.json",
                "global": "~/.cursor/mcp.json",
                "cursor_settings": "Cursor Settings -> Features -> MCP -> Add New MCP Server",
            },
            "config": get_cursor_config(port=port, host=host),
            "command_hint": f"SSE: http://{host}:{port}/mcp?client_name=Cursor | Base URL: http://{host}:{port}/v1",
            "enforcement_rule": {
                "title": "Cursor AI Rule (Prevent Unmonitored Terminal Execution)",
                "description": "Cursor Agent features background terminal execution. Add this rule to ensure all shell commands and script executions route strictly through SafeAI.",
                "rule_files": {
                    "workspace": ".cursorrules (or .cursor/rules/safeai.mdc)",
                    "global": "Cursor Settings -> General -> Rules for AI",
                },
                "content": """# SafeAI Security & Execution Policy
- For all shell commands, scripts, and terminal execution, exclusively use the `safeai` MCP tool (`safeai/bash`).
- Never run commands directly in unmonitored native terminal sessions (`execute_command` or background terminal).
- All command executions must be routed through SafeAI to undergo AST syntax validation, risk evaluation, and human authorization.""",
                "setting_hint": {
                    "path": ".cursor/mcp.json",
                    "snippet": '{\n  "mcpServers": {\n    "safeai": {\n      "url": "http://' + host + ':' + str(port) + '/mcp?client_name=Cursor"\n    }\n  }\n}',
                },
            },
        },
        "windsurf": {
            "id": "windsurf",
            "name": "Windsurf",
            "filename": "windsurf_mcp_config.json",
            "description": "Codeium Cascade MCP connection and agent security proxy.",
            "target_paths": {
                "global": "~/.codeium/windsurf/mcp_config.json",
                "windsurf_settings": "Windsurf Settings -> Cascade -> MCP Plugins",
            },
            "config": get_windsurf_config(port=port, host=host),
            "command_hint": f"Endpoint: http://{host}:{port}/mcp?client_name=Windsurf",
            "enforcement_rule": {
                "title": "Windsurf Cascade Rule (Enforce SafeAI Execution)",
                "description": "Windsurf Cascade can run commands natively. Add this rule to ensure Cascade always routes command-line execution through SafeAI.",
                "rule_files": {
                    "workspace": ".windsurfrules",
                    "global": "~/.codeium/windsurf/memories/global_rules.md",
                },
                "content": """# SafeAI Security & Execution Policy
- For all terminal and shell commands, exclusively use the `safeai` MCP tools (`safeai/bash`).
- Do not execute commands directly via unmonitored Cascade terminal tools.
- Route all command-line operations through SafeAI so that every command is inspected by AST analysis, risk-scored, and subjected to Human-in-the-Loop policies.""",
                "setting_hint": {
                    "path": "~/.codeium/windsurf/mcp_config.json",
                    "snippet": '{\n  "mcpServers": {\n    "safeai": {\n      "serverUrl": "http://' + host + ':' + str(port) + '/mcp?client_name=Windsurf"\n    }\n  }\n}',
                },
            },
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

