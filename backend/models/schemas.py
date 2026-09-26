import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any, Dict
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, ConfigDict


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionRecord(SQLModel, table=True):
    """Represents an active or historical AI client session."""
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    client_name: str = Field(index=True)           # e.g., "Claude Desktop", "Antigravity", "Cursor"
    started_at: datetime = Field(default_factory=utc_now, index=True)
    ended_at: Optional[datetime] = None
    summary: Optional[str] = None                  # Localized executive summary of actions performed
    total_actions: int = Field(default=0)
    blocked_actions: int = Field(default=0)


class ActionLog(SQLModel, table=True):
    """Represents an intercepted, evaluated, and potentially held tool call."""
    __tablename__ = "action_logs"

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    timestamp: datetime = Field(default_factory=utc_now, index=True)
    tool_name: str = Field(index=True)             # e.g., "bash", "write_file", "view_file"
    raw_payload: str                               # JSON-serialized payload/arguments
    plain_language_explanation: str                # Human-friendly explanation in active language
    language_code: str = Field(default="en")       # 'en', 'tr', 'es', 'de', etc.
    risk_score: int = Field(ge=0, le=100)          # Aggregate normalized threat score 0 - 100
    risk_factors: str                              # JSON array string: ["destructive_shell", "env_read"]
    status: str = Field(index=True)                # 'AUTO_APPROVED', 'PENDING', 'APPROVED', 'REJECTED', 'TIMED_OUT'
    user_decision_by: Optional[str] = None         # 'AUTO_POLICY' or 'USER_MANUAL'
    decision_notes: Optional[str] = None
    execution_duration_ms: Optional[int] = None
    execution_result: Optional[str] = None         # Sanitized stdout / stderr / return payload


class PolicyRule(SQLModel, table=True):
    """Security policy rule applied dynamically during evaluation."""
    __tablename__ = "policy_rules"

    id: str = Field(primary_key=True)
    rule_type: str = Field(index=True)             # 'DENY_PATH', 'ALLOW_PATH', 'DENY_COMMAND', 'DENY_DOMAIN'
    pattern: str                                   # Glob or regex pattern
    description: Optional[str] = None
    is_active: bool = Field(default=True)


class ToolSetting(SQLModel, table=True):
    """Per-tool or generic fallback ('*') MCP governance configuration."""
    __tablename__ = "tool_settings"

    id: str = Field(default_factory=lambda: f"tool-{uuid.uuid4().hex[:8]}", primary_key=True)
    tool_name: str = Field(index=True, unique=True)# Specific tool name or '*' for Generic_Tool
    custom_threshold: Optional[int] = None         # 0 - 100 override (None = inherit global)
    downstream_url: Optional[str] = None           # Custom downstream MCP endpoint URL
    bypass_approval: bool = Field(default=False)   # Auto-approve if zero secrets detected
    timeout_ms: int = Field(default=15000)         # Downstream execution timeout
    is_enabled: bool = Field(default=True)         # Enable/disable tool
    description: Optional[str] = None


class SystemConfig(BaseModel):
    """System-wide configuration settings with hot-reload support."""
    model_config = ConfigDict(from_attributes=True)

    approval_threshold: int = 50                   # Hold when risk_score >= threshold
    active_language: str = "auto"                  # 'auto', 'en', 'tr', 'es', 'de', 'fr'
    explainer_mode: str = "plain"                  # "plain", "technical", "off"
    dlp_enabled: bool = True
    approval_timeout_seconds: int = 90             # 0 = infinite (no timeout)

