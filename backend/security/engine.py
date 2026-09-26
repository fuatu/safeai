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
    integrity_score: int = 0                 # 0 - 100 (Destructive ops, Data Loss, Cloud mutations)
    confidentiality_score: int = 0           # 0 - 100 (Sensitive paths/credentials, Cloud secrets)
    availability_score: int = 0              # 0 - 100 (Service disruption, Process kill, Shutdown)
    exfiltration_score: int = 0              # 0 - 100 (Outbound network exfiltration)
    injection_score: int = 0                 # 0 - 100 (Prompt override / escape injection)
    is_unparseable: bool = False             # True if obfuscated or malformed
    evaluation_duration_ms: float = 0.0      # Evaluation latency in milliseconds


class SecurityEngine:
    """
    Evaluates Action_Payloads using AST parsing, heuristic regexes,
    and policy rules across the full CIA Triad (Confidentiality, Integrity, Availability)
    and Data Loss vectors.
    """

    # -------------------------------------------------------------
    # 1. CONFIDENTIALITY VECTORS
    # -------------------------------------------------------------
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

    # Cloud Secrets & IAM Discovery
    CONFIDENTIALITY_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?i)\baws\s+secretsmanager\s+get-secret-value\b"), 85, "[Confidentiality] aws_secretsmanager_read"),
        (re.compile(r"(?i)\baws\s+ssm\s+get-parameter(?:s)?\b"), 80, "[Confidentiality] aws_ssm_parameter_read"),
        (re.compile(r"(?i)\baz\s+keyvault\s+secret\s+show\b"), 85, "[Confidentiality] az_keyvault_secret_read"),
        (re.compile(r"(?i)\baz\s+account\s+get-access-token\b"), 85, "[Confidentiality] az_access_token_read"),
        (re.compile(r"(?i)\bgcloud\s+secrets\s+versions\s+access\b"), 85, "[Confidentiality] gcloud_secret_read"),
        (re.compile(r"(?i)\baws\s+iam\s+(?:list-access-keys|get-login-profile)"), 50, "[Confidentiality] cloud_credential_discovery"),
        (re.compile(r"(?i)\baws\s+iam\s+(?:list-users|list-roles|list-groups|get-account-summary)"), 35, "[Confidentiality] cloud_iam_enumeration"),
        (re.compile(r"(?i)\baws\s+sts\s+get-caller-identity"), 15, "[Confidentiality] cloud_identity_verification"),
    ]

    # Outbound exfiltration patterns requiring exfiltration >= 85
    EXFILTRATION_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?:cat|head|tail|grep|awk|sed)\s+.*\|\s*(?:curl|wget|nc|netcat|ncat|socat)\b"), 85, "[Confidentiality] piped_outbound_exfiltration"),
        (re.compile(r"\bcurl\s+.*(?:-d\s*@|-F\s*.*@|--data-binary\s*@).*"), 85, "[Confidentiality] file_upload_curl_data"),
        (re.compile(r"\bwget\s+.*--post-file=.*"), 85, "[Confidentiality] file_upload_wget_data"),
        (re.compile(r"(?:nc|netcat|ncat|socat)\s+(?:-[a-zA-Z0-9]+\s+)*[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\s+[0-9]+(?:\s*<|\s*\|)"), 90, "[Confidentiality] netcat_raw_socket_transfer"),
        (re.compile(r"(?i)\baws\s+s3\s+sync\s+.*s3://"), 75, "[Confidentiality] aws_s3_sync_outbound"),
    ]

    # -------------------------------------------------------------
    # 2. INTEGRITY & DATA LOSS VECTORS
    # -------------------------------------------------------------
    # Database Wipes & SQL Data Loss
    SQL_DATA_LOSS_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?i)\bDROP\s+(?:TABLE|DATABASE|SCHEMA|VIEW|INDEX)\b"), 90, "[Integrity] sql_drop_table_or_database"),
        (re.compile(r"(?i)\bTRUNCATE\s+(?:TABLE\s+)?[a-zA-Z0-9_\-\.]+\b"), 85, "[Integrity] sql_truncate_table"),
        (re.compile(r"(?i)\bDELETE\s+FROM\s+[a-zA-Z0-9_\-\.]+\b"), 80, "[Integrity] sql_delete_from_table"),
        (re.compile(r"(?i)\bALTER\s+TABLE\s+.*DROP\s+COLUMN\b"), 75, "[Integrity] sql_drop_column"),
        (re.compile(r"(?i)\b(?:FLUSHALL|FLUSHDB)\b"), 85, "[Integrity] redis_flush_database"),
        (re.compile(r"(?i)\b(?:dropDatabase|deleteMany|remove\s*\()\b"), 85, "[Integrity] nosql_data_loss"),
    ]

    # File Deletion & System Integrity Operations (Single, Multi, Recursive)
    DESTRUCTIVE_FILE_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        # Recursive deletion on broad/sensitive directories
        (re.compile(r"(?i)\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+([/~.]+|\.{2}|/etc|/usr|/var|/bin|/sbin|/System|/boot|\$HOME|\*)"), 95, "[Integrity] destructive_recursive_delete_root"),
        (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+"), 75, "[Integrity] destructive_recursive_delete"),
        # Single or multi-file deletion of sensitive or critical database/code assets
        (re.compile(r"(?i)\brm\s+(?:-[a-zA-Z0-9]*\s+)*.*(?:\.db|\.sqlite[0-9]*|\.sql|\.env|\.git|\.pem|\.key|\.crt|\.bak|\.data)\b"), 85, "[Integrity] destructive_critical_file_delete"),
        (re.compile(r"\brm\s+(?:-[a-zA-Z0-9]*f?[a-zA-Z0-9]*\s+)+([^\s\-|&;]+)"), 70, "[Integrity] destructive_file_delete"),
        (re.compile(r"\bunlink\s+[^\s]+"), 70, "[Integrity] file_unlink"),
        (re.compile(r"\b(?:shred|srm)\s+"), 85, "[Integrity] secure_file_shred"),
        (re.compile(r"\btruncate\s+(?:-s\s*0\s+|--size=0\s+)"), 80, "[Integrity] file_truncation"),
        (re.compile(r"\bfind\s+.*-delete\b"), 85, "[Integrity] find_exec_delete"),
        (re.compile(r">\s*(?:[a-zA-Z0-9_\-\./]+\.(?:db|sqlite|sql|env|json|py|js|ts|go|rs|c|cpp))"), 75, "[Integrity] file_truncation_redirect"),
        (re.compile(r"\bmkfs(?:\.[a-zA-Z0-9]+)?\s+"), 95, "[Integrity] disk_format_mkfs"),
        (re.compile(r"\bdd\s+if=.*of=/dev/(?:sd[a-z]|nvme[0-9]n[0-9]|disk[0-9])"), 95, "[Integrity] raw_disk_overwrite_dd"),
        (re.compile(r"\bwipefs\s+"), 90, "[Integrity] disk_wipefs"),
        (re.compile(r"\bchmod\s+-[a-zA-Z]*R[a-zA-Z]*\s+777\s+/"), 85, "[Integrity] world_writable_permissions_root"),
        (re.compile(r"\b(?:fdisk|parted|sfdisk|gdisk)\b"), 80, "[Integrity] partition_modification"),
        (re.compile(r">\s*/dev/(?:sda|sdb|nvme|kmem|mem)"), 95, "[Integrity] device_direct_write"),
    ]

    # Cloud & Infrastructure Resource Mutations (AWS, Azure, GCP, K8s, Terraform)
    CLOUD_MUTATION_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        # AWS
        (re.compile(r"(?i)\baws\s+s3\s+(?:rm|rb)\b"), 85, "[Integrity] aws_s3_delete"),
        (re.compile(r"(?i)\baws\s+rds\s+delete-[a-zA-Z0-9\-]+"), 90, "[Integrity] aws_rds_delete"),
        (re.compile(r"(?i)\baws\s+ec2\s+terminate-instances\b"), 90, "[Integrity] aws_ec2_terminate"),
        (re.compile(r"(?i)\baws\s+(?:dynamodb|cloudformation|lambda|iam|ecs|eks)\s+delete-[a-zA-Z0-9\-]+"), 85, "[Integrity] aws_resource_delete"),
        (re.compile(r"(?i)\baws\s+iam\s+(?:create-|attach-|put-|update-|delete-)"), 85, "[Integrity] cloud_iam_modification"),
        # Azure
        (re.compile(r"(?i)\baz\s+group\s+delete\b"), 95, "[Integrity] az_resource_group_delete"),
        (re.compile(r"(?i)\baz\s+(?:vm|sql\s+db|cosmosdb|storage\s+account|keyvault)\s+delete\b"), 90, "[Integrity] az_resource_delete"),
        (re.compile(r"(?i)\baz\s+storage\s+blob\s+delete(?:-batch)?\b"), 85, "[Integrity] az_blob_delete"),
        # GCP
        (re.compile(r"(?i)\bgcloud\s+compute\s+instances\s+delete\b"), 90, "[Integrity] gcloud_instance_delete"),
        (re.compile(r"(?i)\bgcloud\s+(?:storage\s+rm|sql\s+instances\s+delete|projects\s+delete)\b"), 90, "[Integrity] gcloud_resource_delete"),
        # Kubernetes
        (re.compile(r"(?i)\bkubectl\s+delete\s+(?:namespace|ns|all|pvc|pv|deployment|svc|service)\b"), 85, "[Integrity] k8s_delete_resource"),
        # Terraform & IaC
        (re.compile(r"(?i)\bterraform\s+destroy\b"), 95, "[Integrity] terraform_destroy"),
        (re.compile(r"(?i)\bpulumi\s+destroy\b"), 95, "[Integrity] pulumi_destroy"),
    ]

    # -------------------------------------------------------------
    # 3. AVAILABILITY VECTORS
    # -------------------------------------------------------------
    AVAILABILITY_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?i)\b(?:kill\s+-9|pkill\s+-9|killall\s+-9)\b"), 80, "[Availability] force_kill_process"),
        (re.compile(r"(?i)\b(?:killall|pkill)\b"), 65, "[Availability] kill_processes_by_name"),
        (re.compile(r"(?i)\b(?:shutdown|reboot|poweroff|init\s+[06]|halt)\b"), 95, "[Availability] system_shutdown_or_reboot"),
        (re.compile(r"(?i)\bdocker\s+rm\s+(?:-[a-zA-Z0-9]*f[a-zA-Z0-9]*\s+)"), 75, "[Availability] docker_container_force_remove"),
        (re.compile(r"(?i)\bdocker(?:-compose|\s+compose)\s+down\s+.*-v\b"), 85, "[Availability] docker_compose_down_volumes"),
        (re.compile(r"(?i)\bsystemctl\s+(?:stop|disable|mask)\b"), 75, "[Availability] systemd_service_stop"),
        (re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"), 99, "[Availability] fork_bomb"),
    ]

    # -------------------------------------------------------------
    # 4. INJECTION & OBFUSCATION VECTORS
    # -------------------------------------------------------------
    INJECTION_PATTERNS: List[Tuple[re.Pattern, int, str]] = [
        (re.compile(r"(?i)\bignore\s+(?:all\s+)?previous\s+instructions\b"), 85, "[Injection] prompt_injection_ignore_instructions"),
        (re.compile(r"(?i)\bdisregard\s+(?:all\s+)?prior\s+instructions\b"), 85, "[Injection] prompt_injection_disregard_instructions"),
        (re.compile(r"(?i)\bsystem\s+prompt\s+override\b"), 90, "[Injection] prompt_injection_system_override"),
        (re.compile(r"(?i)\byou\s+are\s+now\s+in\s+dan\s+mode\b"), 85, "[Injection] prompt_injection_dan_mode"),
        (re.compile(r"(?i)\bjailbreak\b"), 75, "[Injection] prompt_injection_jailbreak"),
        (re.compile(r"[\U000e0000-\U000e007f]"), 80, "[Injection] invisible_unicode_tags"),
        (re.compile(r"(?:\x1b\[[0-9;]*[a-zA-Z]|\033\[[0-9;]*[a-zA-Z])"), 75, "[Injection] ansi_escape_injection"),
    ]

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
        availability_score = 0
        exfiltration_score = 0
        injection_score = 0
        is_unparseable = False

        # Extract text representations of payload arguments
        combined_text = self._flatten_payload(payload)

        # Unpack embedded code (e.g., python -c "...", node -e "...", bash -c "...") for deep scanning
        command_str = self._extract_command(tool_name, payload)
        if command_str:
            embedded_matches = re.findall(r"""(?:python[0-9.]*|node|ruby|bash|sh|zsh)\s+(?:-c|-e)\s+["'](.*?)["']""", command_str, re.DOTALL)
            for emb in embedded_matches:
                combined_text += f" {emb}"

        # 1. Obfuscation & Unparseable Detection (Req 2.6)
        for pattern in self.OBFUSCATION_PATTERNS:
            if pattern.search(combined_text):
                is_unparseable = True
                factors.append("obfuscated_or_unparseable_payload")
                break

        # Shell command AST analysis if bash / shell execution tool
        if command_str:
            ast_result = self._analyze_shell_ast(command_str)
            if ast_result.get("is_unparseable"):
                is_unparseable = True
                factors.append("shell_ast_parse_failure")
            
            integrity_score = max(integrity_score, ast_result.get("integrity_score", 0))
            confidentiality_score = max(confidentiality_score, ast_result.get("confidentiality_score", 0))
            availability_score = max(availability_score, ast_result.get("availability_score", 0))
            exfiltration_score = max(exfiltration_score, ast_result.get("exfiltration_score", 0))
            factors.extend(ast_result.get("factors", []))

        # 2. Integrity & Data Loss Scrutiny (SQL, Filesystem, Cloud Mutations)
        for pattern, score, factor_name in self.SQL_DATA_LOSS_PATTERNS:
            if pattern.search(combined_text):
                integrity_score = max(integrity_score, score)
                factors.append(factor_name)

        for pattern, score, factor_name in self.DESTRUCTIVE_FILE_PATTERNS:
            if pattern.search(combined_text):
                integrity_score = max(integrity_score, score)
                factors.append(factor_name)

        for pattern, score, factor_name in self.CLOUD_MUTATION_PATTERNS:
            if pattern.search(combined_text):
                integrity_score = max(integrity_score, score)
                factors.append(factor_name)

        # 3. Confidentiality Scrutiny (Sensitive Paths, Cloud Secrets, IAM Discovery)
        sensitive_matches = self._detect_sensitive_paths(combined_text)
        if sensitive_matches:
            confidentiality_score = max(confidentiality_score, 80)
            for sm in sensitive_matches:
                factors.append(f"sensitive_path:{sm}")

        for pattern, score, factor_name in self.CONFIDENTIALITY_PATTERNS:
            if pattern.search(combined_text):
                confidentiality_score = max(confidentiality_score, score)
                factors.append(factor_name)

        for pattern, score, factor_name in self.EXFILTRATION_PATTERNS:
            if pattern.search(combined_text):
                exfiltration_score = max(exfiltration_score, score)
                factors.append(factor_name)

        # 4. Availability Scrutiny (Service Disruption, Process Termination, Shutdown)
        for pattern, score, factor_name in self.AVAILABILITY_PATTERNS:
            if pattern.search(combined_text):
                availability_score = max(availability_score, score)
                factors.append(factor_name)

        # 5. Prompt Injection Scrutiny
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
            composite_score = 90
        else:
            composite_score = max(
                integrity_score,
                confidentiality_score,
                availability_score,
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
            availability_score=availability_score,
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
        availability_score = 0
        exfiltration_score = 0
        is_unparseable = False

        if not command_str.strip():
            return {
                "factors": factors,
                "integrity_score": integrity_score,
                "confidentiality_score": confidentiality_score,
                "availability_score": availability_score,
                "exfiltration_score": exfiltration_score,
                "is_unparseable": False,
            }

        # Try parsing with bashlex first
        if bashlex is not None:
            try:
                parts = bashlex.parse(command_str)
            except Exception:
                # If bashlex fails, check if shlex can parse it
                try:
                    shlex.split(command_str)
                except Exception:
                    # Both failed: truly unparseable / malformed syntax
                    is_unparseable = True
                    return {
                        "factors": ["[Integrity] unparseable_shell_syntax"],
                        "integrity_score": 0,
                        "confidentiality_score": 0,
                        "availability_score": 0,
                        "exfiltration_score": 0,
                        "is_unparseable": True,
                    }

        # Inspect token streams for CIA threats
        try:
            tokens = shlex.split(command_str)
            for i, token in enumerate(tokens):
                # File deletions
                if token in ("rm", "/bin/rm", "/usr/bin/rm"):
                    remaining = tokens[i+1:]
                    if any(arg in ("-rf", "-fr", "-r", "-R") for arg in remaining):
                        integrity_score = max(integrity_score, 75)
                        factors.append("[Integrity] ast_detected_rm_recursive")
                    elif any(any(ext in arg for ext in (".db", ".sqlite", ".sql", ".env", ".key", ".pem")) for arg in remaining):
                        integrity_score = max(integrity_score, 85)
                        factors.append("[Integrity] ast_detected_critical_file_delete")
                    elif any(not arg.startswith("-") for arg in remaining):
                        integrity_score = max(integrity_score, 70)
                        factors.append("[Integrity] ast_detected_file_delete")
                elif token in ("unlink", "shred", "srm"):
                    integrity_score = max(integrity_score, 75)
                    factors.append("[Integrity] ast_detected_file_wipe")
                elif token in ("mkfs", "wipefs"):
                    integrity_score = max(integrity_score, 95)
                    factors.append("[Integrity] ast_detected_disk_format")
                elif token in ("kill", "pkill", "killall", "/bin/kill", "/usr/bin/kill"):
                    availability_score = max(availability_score, 80)
                    factors.append("[Availability] ast_detected_process_termination")
                elif token in ("terraform", "pulumi") and any(arg == "destroy" for arg in tokens[i+1:]):
                    integrity_score = max(integrity_score, 95)
                    factors.append("[Integrity] ast_detected_iac_destroy")
        except Exception:
            pass

        return {
            "factors": factors,
            "integrity_score": integrity_score,
            "confidentiality_score": confidentiality_score,
            "availability_score": availability_score,
            "exfiltration_score": exfiltration_score,
            "is_unparseable": is_unparseable,
        }

