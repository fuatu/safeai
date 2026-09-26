"""Client identification and canonicalization resolver for SafeAI MCP Gateway."""

from typing import Optional


def canonicalize_client_name(raw_name: Optional[str]) -> Optional[str]:
    """
    Standardizes client identifiers from URL query parameters (?client_name=...),
    HTTP headers (User-Agent), and MCP handshake clientInfo into uniform display names.

    Examples:
      - 'GithubCopilot', 'copilot', 'vscode' -> 'VS Code + GitHub Copilot'
      - 'antigravity', 'GoogleAntigravity'   -> 'Google Antigravity IDE'
      - 'hermes', 'HermesAgent'              -> 'Hermes Agent'
      - 'claude', 'ClaudeDesktop'            -> 'Claude Desktop'
      - 'cursor', 'windsurf'                 -> 'Cursor'

    Generic strings ('mcp', 'mcp-client', 'ai client', 'client', 'generic', '')
    return None so they never overwrite known client identities.
    """
    if not raw_name:
        return None

    cleaned = str(raw_name).strip()
    if not cleaned:
        return None

    lower = cleaned.lower()

    # Generic or empty client identifiers sent by default MCP client libraries
    if lower in (
        "mcp",
        "mcp-client",
        "mcp_client",
        "mcp client",
        "ai client",
        "client",
        "generic",
        "unknown",
        "none",
        "null",
    ):
        return None

    # GitHub Copilot / Visual Studio Code
    if any(k in lower for k in ("copilot", "github", "vscode", "visual studio code", "code")):
        return "VS Code + GitHub Copilot"

    # Google Antigravity IDE
    if any(k in lower for k in ("antigravity", "gemini")):
        return "Google Antigravity IDE"

    # Hermes Agent
    if any(k in lower for k in ("hermes", "nous")):
        return "Hermes Agent"

    # Anthropic Claude Desktop
    if any(k in lower for k in ("claude", "anthropic")):
        return "Claude Desktop"

    # Cursor / Windsurf
    if any(k in lower for k in ("cursor", "windsurf")):
        return "Cursor"

    # Preserve custom user-specified agent names
    if any(c.isupper() for c in cleaned[1:]):
        return cleaned
    return cleaned.title()
