"""Unit tests for client identification and canonicalization resolver."""

import pytest
from backend.gateway.client_resolver import canonicalize_client_name


def test_canonicalize_copilot_variations():
    assert canonicalize_client_name("GithubCopilot") == "VS Code + GitHub Copilot"
    assert canonicalize_client_name("githubcopilot") == "VS Code + GitHub Copilot"
    assert canonicalize_client_name("copilot") == "VS Code + GitHub Copilot"
    assert canonicalize_client_name("vscode") == "VS Code + GitHub Copilot"
    assert canonicalize_client_name("Visual Studio Code") == "VS Code + GitHub Copilot"


def test_canonicalize_antigravity_variations():
    assert canonicalize_client_name("antigravity") == "Google Antigravity IDE"
    assert canonicalize_client_name("GoogleAntigravity") == "Google Antigravity IDE"
    assert canonicalize_client_name("gemini-cli") == "Google Antigravity IDE"


def test_canonicalize_hermes_variations():
    assert canonicalize_client_name("hermes") == "Hermes Agent"
    assert canonicalize_client_name("HermesAgent") == "Hermes Agent"


def test_canonicalize_claude_and_cursor():
    assert canonicalize_client_name("claude") == "Claude Desktop"
    assert canonicalize_client_name("ClaudeDesktop") == "Claude Desktop"
    assert canonicalize_client_name("cursor") == "Cursor"
    assert canonicalize_client_name("windsurf") == "Cursor"


def test_canonicalize_generic_strings_return_none():
    assert canonicalize_client_name("mcp") is None
    assert canonicalize_client_name("mcp-client") is None
    assert canonicalize_client_name("mcp client") is None
    assert canonicalize_client_name("AI Client") is None
    assert canonicalize_client_name("client") is None
    assert canonicalize_client_name("generic") is None
    assert canonicalize_client_name("") is None
    assert canonicalize_client_name(None) is None


def test_canonicalize_custom_client_names():
    assert canonicalize_client_name("MyAutonomousBot") == "MyAutonomousBot"
    assert canonicalize_client_name("data-pipeline-agent") == "Data-Pipeline-Agent"
