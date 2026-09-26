"""Data Loss Prevention (DLP) and secret masking scanner."""

import math
import re
from typing import Any, Dict, List, Tuple


class DLPMasker:
    """Detects and redacts sensitive credentials, private keys, and high-entropy secrets."""

    # Pre-compiled high-confidence secret patterns
    PATTERNS: List[Tuple[str, re.Pattern, str]] = [
        # SSH / RSA / DSA / EC Private Keys
        (
            "PRIVATE_KEY",
            re.compile(
                r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
                re.MULTILINE,
            ),
            "[REDACTED_PRIVATE_KEY]",
        ),
        # AWS Access Key ID
        (
            "AWS_KEY",
            re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
            "[REDACTED_AWS_KEY]",
        ),
        # GitHub Personal Access Token / fine-grained tokens
        (
            "GITHUB_TOKEN",
            re.compile(r"(?<![a-zA-Z0-9])(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36,255}(?![a-zA-Z0-9])"),
            "[REDACTED_GITHUB_TOKEN]",
        ),
        (
            "GITHUB_PAT",
            re.compile(r"(?<![a-zA-Z0-9])github_pat_[a-zA-Z0-9_]{50,255}(?![a-zA-Z0-9])"),
            "[REDACTED_GITHUB_TOKEN]",
        ),
        # OpenAI API Key
        (
            "OPENAI_KEY",
            re.compile(r"(?<![a-zA-Z0-9])sk-(?:proj-|svcacct-)?[a-zA-Z0-9_\-]{20,}(?![a-zA-Z0-9_\-])"),
            "[REDACTED_OPENAI_KEY]",
        ),
        # Slack Tokens
        (
            "SLACK_TOKEN",
            re.compile(r"(?<![a-zA-Z0-9])xox[baprs]-[0-9a-zA-Z]{10,48}(?![a-zA-Z0-9])"),
            "[REDACTED_SLACK_TOKEN]",
        ),
        # Bearer Authorization Tokens
        (
            "BEARER_TOKEN",
            re.compile(r"(?i)\bBearer\s+([a-zA-Z0-9_\-\.]{20,})"),
            "Bearer [REDACTED_BEARER_TOKEN]",
        ),
        # Generic Secret/Password assignments in URLs or configs
        (
            "DB_URL_PASSWORD",
            re.compile(r"(://[^:]+:)([^@\s/]+)(@)"),
            r"\1[REDACTED_PASSWORD]\3",
        ),
        # Basic auth tokens in headers
        (
            "BASIC_AUTH",
            re.compile(r"(?i)\bBasic\s+([a-zA-Z0-9+/=]{20,})"),
            "Basic [REDACTED_BASIC_AUTH]",
        ),
        # Key / Token assignment patterns in env or config
        (
            "ENV_SECRET_ASSIGNMENT",
            re.compile(
                r"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-~!@#$%^&*()+=/]{16,})['\"]?"
            ),
            r"secret_key=[REDACTED_SECRET]",
        ),
    ]

    @staticmethod
    def _shannon_entropy(data: str) -> float:
        """Calculates the Shannon entropy of a string."""
        if not data:
            return 0.0
        entropy = 0.0
        for x in set(data):
            p_x = float(data.count(x)) / len(data)
            if p_x > 0:
                entropy += -p_x * math.log2(p_x)
        return entropy

    def contains_secrets(self, text: str) -> bool:
        """Checks if text contains known secret patterns."""
        if not text:
            return False
        for _, pattern, _ in self.PATTERNS:
            if pattern.search(text):
                return True
        return False

    def redact_secrets(self, text: str) -> str:
        """
        Replaces all detected credentials, private keys, and secret tokens
        with structured redaction tokens.
        """
        if not isinstance(text, str) or not text:
            return text

        redacted = text
        for _, pattern, replacement in self.PATTERNS:
            redacted = pattern.sub(replacement, redacted)

        return redacted

    def redact_payload(self, payload: Any) -> Any:
        """Recursively traverses dictionaries, lists, or strings and redacts secrets."""
        if isinstance(payload, str):
            return self.redact_secrets(payload)
        elif isinstance(payload, dict):
            return {k: self.redact_payload(v) for k, v in payload.items()}
        elif isinstance(payload, list):
            return [self.redact_payload(item) for item in payload]
        return payload
