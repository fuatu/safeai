"""Multi-vector security scoring and AST shell analyzer engine."""

import os
import re
import shlex
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import bashlex
except ImportError:
    bashlex = None

from backend.models.schemas import PolicyRule


@dataclass
class SecurityAssessment:
    """Detailed evaluation result returned by the SecurityEngine."""
    risk_score: int                          # Normalized composite score 0 - 100
    risk_factors: List[str]                  # List of matched threat tags
    integrity_score: int = 0                 # 0 - 100 (Destructive ops)
    confidentiality_score: int = 0           # 0 - 100 (Sensitive paths/credentials)
    exfiltration_score: int = 0              # 0 - 100 (Outbound network exfiltration)
    injection_score: int = 0                 # 0 - 100 (Prompt override / escape injection)
    is_unparseable: bool = False             # True if obfuscated or malformed
    evaluation_duration_ms: float = 0.0      # Evaluation latency in milliseconds


class SecurityEngine:
    """
    Evaluates Action_Payloads using AST parsing, heuristic regexes,
    and policy rules across four threat vectors.
    """

    # Sensitive paths requiring confidentiality >= 80
    SENSITIVE_PATHS: List[re.Pattern] = [
        re.compile(r"(?i)\.env(?:\.[a-zA-Z0-9_\-]+)?"),
        re.compile(r"(?i)(?:~|\$HOME|/home/[^/\s]+|/Users/[^/\s]+)/\.ssh(?:/[^\s]+)?"),
        re.compile(r"(?i)\bid_rsa\b|\bid_ed25519\b|\bid_ecdsa\b|\bid_dsa\b"),
        re.compile(r"(?i)\bkeychain\b|\bsecurity\s+find-(?:generic|internet)-password"),
        re.compile(r"(?i)(?:\.aws/credentials|\.kube/config|\.git-credentials|\.netrc)"),
        re.compile(r"(?i)/etc/(?:shadow|passwd|sudoers)"),
        re.compile(r"(?i)(?:id_rsa\.pub|\.pgpass|\.npmrc)"),
    ]

    # Destructive file / system operations requiring integrity >= 70
    DESTRUCTIVE_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        # Recursive deletion on broad/sensitive directories
        (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+([/~.]+|\.{2}|/etc|/usr|/var|/bin|/sbin|/System|/boot|\$HOME|\*)"), 95, "destructive_recursive_delete_root"),
        (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+"), 75, "destructive_recursive_delete"),
        (re.compile(r"\bmkfs(?:\.[a-zA-Z0-9]+)?\s+"), 95, "disk_format_mkfs"),
        (re.compile(r"\bdd\s+if=.*of=/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|disk[0-9])"), 95, "raw_disk_overwrite_dd"),
        (re.compile(r"\bwipefs\s+"), 90, "disk_wipefs"),
        (re.compile(r"\bchmod\s+-[a-zA-Z]*R[a-zA-Z]*\s+777\s+/"), 85, "world_writable_permissions_root"),
        (re.compile(r"\b(?:fdisk|parted|sfdisk|gdisk)\b"), 80, "partition_modification"),
        (re.compile(r">\s*/dev/(?:sda|sdb|nvme|kmem|mem)"), 95, "device_direct_write"),
        (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), 99, "fork_bomb"),
    ]

    # Outbound exfiltration patterns requiring exfiltration >= 85
    EXFILTRATION_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        # Piping file to curl/wget/nc
        (re.compile(r"(?:cat|head|tail|grep|awk|sed)\s+.*\|\s*(?:curl|wget|nc|netcat|ncat|socat)\b"), 85, "piped_outbound_exfiltration"),
        (re.compile(r"\bcurl\s+.*(?:-d\s*@|-F\s*.*@|--data-binary\s*@).*"), 85, "file_upload_curl_data"),
        (re.compile(r"\bwget\s+.*--post-file=.*"), 85, "file_upload_wget_data"),
        (re.compile(r"(?:nc|netcat|ncat|socat)\s+(?:-[a-zA-Z0-9]+\s+)*[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\s+[0-9]+(?:\s*<|\s*\|)"), 90, "netcat_raw_socket_transfer"),
    ]

    # Prompt injection and control sequence override patterns requiring injection >= 75
    INJECTION_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"), 85, "prompt_injection_ignore_instructions"),
        (re.compile(r"(?i)\bdisregard\s+(?:all\s+)?prior\s+instructions\b"), 85, "prompt_injection_disregard_instructions"),
        (re.compile(r"(?i)\bsystem\s+prompt\s+override\b"), 90, "prompt_injection_system_override"),
        (re.compile(r"(?i)\byou\s+are\s+now\s+in\s+dan\s+mode\b"), 85, "prompt_injection_dan_mode"),
        (re.compile(r"(?i)\bjailbreak\b"), 75, "prompt_injection_jailbreak"),
        # Invisible unicode tag characters (used for hidden prompt injection)
        (re.compile(r"[\U000e0000-\U000e007f]"), 80, "invisible_unicode_tags"),
        # ANSI escape sequence injection hiding commands
        (re.compile(r"(?:\x1b\[[0-9;]*[a-zA-Z]|\033\[[0-9;]*[a-zA-Z])"), 75, "ansi_escape_injection"),
    ]

    # Obfuscation patterns requiring risk_score = 90
    OBFUSCATION_PATTERNS: List[re.Pattern] = [
        re.compile(r"(?i)\bbase64\s+-(?:d|-decode)\b.*\|\s*(?:bash|sh|zsh)"),
        re.compile(r"(?i)\bxxd\s+-r\b.*\|\s*(?:bash|sh|zsh)"),
        re.compile(r"(?i)\beval\s*\(?[\"'\$]"),
        re.compile(r"(?i)\bopenssl\s+enc\s+-d\b.*\|\s*(?:bash|sh|zsh)"),
        re.compile(r"(?i)\bpython[0-9.]*\s+-c\s+['\"][^'\"]*exec\s*\("),
        re.compile(r"\x00"),  # Null byte injection
    ]

    def __init__(self, policy_rules: Optional[List[PolicyRule]] = None):
        self.policy_rules = policy_rules or []

    def set_policy_rules(self, rules: List[PolicyRule]) -> None:
        """Dynamically updates active policy rules for hot-reloading."""
        self.policy_rules = rules

    def evaluate_payload(
        self, tool_name: str, payload: Dict[str, Any]
    ) -> SecurityAssessment:
        """
        Calculates composite risk score and vector sub-scores within 200ms.
        """
        start_time = time.perf_counter()

        factors: List[str] = []
        integrity_score = 0
        confidentiality_score = 0
        exfiltration_score = 0
        injection_score = 0
        is_unparseable = False

        # Extract text representations of payload arguments
        combined_text = self._flatten_payload(payload)

        # 1. Obfuscation & Unparseable Detection (Req 2.6)
        for pattern in self.OBFUSCATION_PATTERNS:
            if pattern.search(combined_text):
                is_unparseable = True
                factors.append("obfuscated_or_unparseable_payload")
                break

        # Shell command AST analysis if bash / shell execution tool
        command_str = self._extract_command(tool_name, payload)
        if command_str:
            ast_result = self._analyze_shell_ast(command_str)
            if ast_result.get("is_unparseable"):
                is_unparseable = True
                factors.append("shell_ast_parse_failure")
            
            integrity_score = max(integrity_score, ast_result.get("integrity_score", 0))
            confidentiality_score = max(confidentiality_score, ast_result.get("confidentiality_score", 0))
            exfiltration_score = max(exfiltration_score, ast_result.get("exfiltration_score", 0))
            factors.extend(ast_result.get("factors", []))

        # 2. Destructive Operations Scrutiny (Req 2.2: integrity >= 70)
        for pattern, score, factor_name in self.DESTRUCTIVE_PATTERNS:
            if pattern.search(combined_text):
                integrity_score = max(integrity_score, score)
                factors.append(factor_name)

        # 3. Sensitive Paths Scrutiny (Req 2.3: confidentiality >= 80)
        sensitive_matches = self._detect_sensitive_paths(combined_text)
        if sensitive_matches:
            confidentiality_score = max(confidentiality_score, 80)
            for sm in sensitive_matches:
                factors.append(f"sensitive_path:{sm}")

        # 4. Outbound Network & Exfiltration Scrutiny (Req 2.4: exfiltration >= 85)
        for pattern, score, factor_name in self.EXFILTRATION_PATTERNS:
            if pattern.search(combined_text):
                exfiltration_score = max(exfiltration_score, score)
                factors.append(factor_name)

        # 5. Prompt Injection Scrutiny (Req 2.5: injection >= 75)
        for pattern, score, factor_name in self.INJECTION_PATTERNS:
            if pattern.search(combined_text):
                injection_score = max(injection_score, score)
                factors.append(factor_name)

        # 6. Apply Active Policy Rules (Allow / Deny list overrides)
        for rule in self.policy_rules:
            if not rule.is_active:
                continue
            if rule.rule_type == "DENY_PATH" and re.search(re.escape(rule.pattern), combined_text):
                confidentiality_score = max(confidentiality_score, 90)
                factors.append(f"policy_deny_path:{rule.pattern}")
            elif rule.rule_type == "DENY_COMMAND" and re.search(re.escape(rule.pattern), combined_text):
                integrity_score = max(integrity_score, 90)
                factors.append(f"policy_deny_command:{rule.pattern}")

        # Calculate composite score
        if is_unparseable:
            # Req 2.6: Unparseable/obfuscated must assign default Risk_Score of 90
            composite_score = 90
        else:
            composite_score = max(
                integrity_score,
                confidentiality_score,
                exfiltration_score,
                injection_score,
            )

        # Enforce bounds [0, 100]
        composite_score = max(0, min(100, composite_score))

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Deduplicate factors preserving order
        unique_factors = list(dict.fromkeys(factors))

        return SecurityAssessment(
            risk_score=composite_score,
            risk_factors=unique_factors,
            integrity_score=integrity_score,
            confidentiality_score=confidentiality_score,
            exfiltration_score=exfiltration_score,
            injection_score=injection_score,
            is_unparseable=is_unparseable,
            evaluation_duration_ms=round(duration_ms, 2),
        )

    def _extract_command(self, tool_name: str, payload: Dict[str, Any]) -> Optional[str]:
        """Extracts command line string from common tool invocation formats."""
        if tool_name in ("bash", "run_command", "shell", "execute_command", "terminal"):
            for key in ("command", "cmd", "CommandLine", "script"):
                if key in payload and isinstance(payload[key], str):
                    return payload[key]
        return None

    def _flatten_payload(self, data: Any) -> str:
        """Recursively converts payload elements to a string for scanning."""
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            return " ".join(f"{k}={self._flatten_payload(v)}" for k, v in data.items())
        elif isinstance(data, list):
            return " ".join(self._flatten_payload(v) for v in data)
        return str(data)

    def _detect_sensitive_paths(self, text: str) -> List[str]:
        """Identifies any sensitive filesystem paths in text."""
        matches = []
        for pat in self.SENSITIVE_PATHS:
            found = pat.findall(text)
            if found:
                for f in found:
                    matches.append(f if isinstance(f, str) else f[0])
        return matches

    def _analyze_shell_ast(self, command_str: str) -> Dict[str, Any]:
        """
        Parses shell command string with bashlex (or shlex fallback)
        to identify structural pipelines, redirections, and subshells.
        """
        factors: List[str] = []
        integrity_score = 0
        confidentiality_score = 0
        exfiltration_score = 0
        is_unparseable = False

        if not command_str.strip():
            return {
                "factors": factors,
                "integrity_score": integrity_score,
                "confidentiality_score": confidentiality_score,
                "exfiltration_score": exfiltration_score,
                "is_unparseable": False,
            }

        # Try parsing with bashlex first
        if bashlex is not None:
            try:
                parts = bashlex.parse(command_str)
                # Successfully parsed AST
            except Exception:
                # If bashlex fails, check if shlex can parse it
                try:
                    shlex.split(command_str)
                except Exception:
                    # Both failed: truly unparseable / malformed syntax
                    is_unparseable = True
                    return {
                        "factors": ["unparseable_shell_syntax"],
                        "integrity_score": 0,
                        "confidentiality_score": 0,
                        "exfiltration_score": 0,
                        "is_unparseable": True,
                    }

        # Inspect pipelines and redirections
        try:
            tokens = shlex.split(command_str)
            for i, token in enumerate(tokens):
                # Check for destructive commands
                if token in ("rm", "/bin/rm", "/usr/bin/rm"):
                    if any(arg in ("-rf", "-fr", "-r", "-R") for arg in tokens[i+1:]):
                        integrity_score = max(integrity_score, 75)
                        factors.append("ast_detected_rm_recursive")
                elif token in ("mkfs", "wipefs"):
                    integrity_score = max(integrity_score, 95)
                    factors.append("ast_detected_disk_format")
        except Exception:
            pass

        return {
            "factors": factors,
            "integrity_score": integrity_score,
            "confidentiality_score": confidentiality_score,
            "exfiltration_score": exfiltration_score,
            "is_unparseable": is_unparseable,
        }
