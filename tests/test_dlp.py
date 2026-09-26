"""Tests for DLPMasker secret redaction."""

import pytest
from backend.security.dlp import DLPMasker


def test_dlp_aws_key_redaction():
    masker = DLPMasker()
    raw = "Deploying to AWS using AKIAIOSFODNN7EXAMPLE key now."
    redacted = masker.redact_secrets(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_dlp_openai_key_redaction():
    masker = DLPMasker()
    raw = "export OPENAI_API_KEY=sk-proj-abc123def456ghi789jkl012mno345pqr"
    redacted = masker.redact_secrets(raw)
    assert "sk-proj-abc123def456ghi789jkl012mno345pqr" not in redacted
    assert "[REDACTED_OPENAI_KEY]" in redacted


def test_dlp_github_token_redaction():
    masker = DLPMasker()
    raw = "curl -H 'Authorization: token ghp_123456789012345678901234567890123456' https://api.github.com"
    redacted = masker.redact_secrets(raw)
    assert "ghp_123456789012345678901234567890123456" not in redacted
    assert "[REDACTED_GITHUB_TOKEN]" in redacted


def test_dlp_private_key_redaction():
    masker = DLPMasker()
    raw = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Y1o0z7uK+aHq1...fake...fake...\n"
        "-----END RSA PRIVATE KEY-----"
    )
    redacted = masker.redact_secrets(raw)
    assert "MIIEowIBAAKCAQEA" not in redacted
    assert "[REDACTED_PRIVATE_KEY]" in redacted


def test_dlp_bearer_token_redaction():
    masker = DLPMasker()
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake"
    redacted = masker.redact_secrets(raw)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted
    assert "Bearer [REDACTED_BEARER_TOKEN]" in redacted


def test_dlp_db_password_redaction():
    masker = DLPMasker()
    raw = "DATABASE_URL=postgres://admin:super_secret_password_123@db.internal:5432/safeai"
    redacted = masker.redact_secrets(raw)
    assert "super_secret_password_123" not in redacted
    assert "[REDACTED_PASSWORD]" in redacted


def test_dlp_payload_recursive_redaction():
    masker = DLPMasker()
    payload = {
        "command": "curl -H 'Authorization: Bearer abcdef1234567890abcdef1234567890' https://example.com",
        "nested": {
            "token": "ghp_123456789012345678901234567890123456",
            "list": ["AKIAIOSFODNN7EXAMPLE", "safe string"]
        }
    }
    redacted = masker.redact_payload(payload)
    assert "[REDACTED_BEARER_TOKEN]" in redacted["command"]
    assert "[REDACTED_GITHUB_TOKEN]" == redacted["nested"]["token"]
    assert "[REDACTED_AWS_KEY]" == redacted["nested"]["list"][0]
    assert "safe string" == redacted["nested"]["list"][1]
