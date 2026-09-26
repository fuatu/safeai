"""Persistent SQLite audit store implementation using SQLModel."""

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any

from sqlmodel import Session, SQLModel, create_engine, select

from backend.models.schemas import ActionLog, PolicyRule, SessionRecord, ToolSetting


class AuditStore:
    """Manages persistent SQLite storage for sessions, action logs, and policy rules."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            configured = os.environ.get("SAFEAI_DB_PATH", "/data/safeai.db")
            # If default /data path is not writable or doesn't exist outside docker, fallback to ./data
            try:
                parent = Path(configured).parent
                parent.mkdir(parents=True, exist_ok=True)
                test_file = parent / ".write_test"
                test_file.touch()
                test_file.unlink()
                self.db_path = configured
            except (PermissionError, OSError):
                local_dir = Path("./data")
                local_dir.mkdir(parents=True, exist_ok=True)
                self.db_path = str(local_dir / "safeai.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.database_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        self._init_db()

    def _init_db(self) -> None:
        """Creates tables if they do not exist."""
        SQLModel.metadata.create_all(self.engine)
        # Migrate schema safely if 'title' column does not exist
        try:
            with self.engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("ALTER TABLE sessions ADD COLUMN title VARCHAR"))
                conn.commit()
        except Exception:
            pass  # Already exists or table created with title
        self._consolidate_fragmented_sessions()

    def _consolidate_fragmented_sessions(self) -> None:
        """
        Consolidates fragmented tool sessions into their parent chat sessions
        and removes orphaned empty sessions to keep the audit history clean and unified.
        """
        try:
            with self.get_session() as session:
                all_sessions = list(session.exec(select(SessionRecord)).all())
                now = datetime.now(timezone.utc)
                for s in all_sessions:
                    action_count = len(list(session.exec(select(ActionLog.id).where(ActionLog.session_id == s.id)).all()))
                    st = s.started_at if s.started_at and s.started_at.tzinfo else (s.started_at.replace(tzinfo=timezone.utc) if s.started_at else now)
                    age = (now - st).total_seconds()

                    if action_count == 0 and (age > 60 or "Hermes" in (s.client_name or "") or s.client_name in ("MCP Client", "mcp", "AI Client")):
                        session.delete(s)
                        continue

                    if s.title and ("bash (" in s.title or "read_file" in s.title):
                        prefix = "antigravity-" if "Antigravity" in (s.client_name or "") else ("copilot-" if "Copilot" in (s.client_name or "") else None)
                        if prefix:
                            matching = list(session.exec(
                                select(SessionRecord)
                                .where(SessionRecord.id.startswith(prefix))
                                .where(SessionRecord.id != s.id)
                            ).all())
                            if matching:
                                closest = min(matching, key=lambda p: abs((p.started_at - s.started_at).total_seconds()) if p.started_at and s.started_at else 999999)
                                acts = list(session.exec(select(ActionLog).where(ActionLog.session_id == s.id)).all())
                                for a in acts:
                                    a.session_id = closest.id
                                    session.add(a)
                                session.delete(s)
                                continue

                    s.total_actions = action_count
                    session.add(s)

                session.commit()
        except Exception:
            pass

    def get_session(self) -> Session:
        """Returns a new database session with non-expiring attributes."""
        return Session(self.engine, expire_on_commit=False)

    # ---------------------------------------------------------
    # Session Operations
    # ---------------------------------------------------------

    def create_session(self, session_record: SessionRecord) -> SessionRecord:
        """Stores a new session record."""
        with self.get_session() as session:
            session.add(session_record)
            session.commit()
            session.refresh(session_record)
            return session_record

    def get_session_by_id(self, session_id: str) -> Optional[SessionRecord]:
        """Retrieves a session record by its primary key ID."""
        with self.get_session() as session:
            statement = select(SessionRecord).where(SessionRecord.id == session_id)
            return session.exec(statement).first()

    def update_session(self, session_record: SessionRecord) -> SessionRecord:
        """Updates an existing session record."""
        with self.get_session() as session:
            merged = session.merge(session_record)
            session.commit()
            return merged

    def list_sessions(self, limit: int = 50) -> List[SessionRecord]:
        """Lists recent sessions ordered by start time descending."""
        with self.get_session() as session:
            statement = select(SessionRecord).order_by(SessionRecord.started_at.desc()).limit(limit)
            records = list(session.exec(statement).all())
            now = datetime.now(timezone.utc)
            filtered = []
            updated = False
            for r in records:
                if r.client_name in ("AI Client", "AI Client..."):
                    r.client_name = "VS Code + GitHub Copilot"
                    updated = True

                if not r.title:
                    date_str = r.started_at.strftime("%b %d, %H:%M") if r.started_at else ""
                    r.title = f"{r.client_name} (Connected · {date_str})" if date_str else f"{r.client_name} (Connected)"
                    updated = True

                # Ensure total_actions matches actual action count
                real_action_count = len(list(session.exec(select(ActionLog.id).where(ActionLog.session_id == r.id)).all()))
                if r.total_actions != real_action_count:
                    r.total_actions = real_action_count
                    updated = True

                # Filter out generic 0-action MCP client probes so they never clutter the UI
                if r.total_actions == 0 and r.client_name in ("MCP Client", "mcp", "AI Client"):
                    continue

                # Skip empty dangling connection stubs with 0 actions older than 1 min to keep directory clean
                if r.total_actions == 0 and r.started_at and ("(Connected" in (r.title or "")):
                    st = r.started_at if r.started_at.tzinfo else r.started_at.replace(tzinfo=timezone.utc)
                    age_seconds = (now - st).total_seconds()
                    if age_seconds > 60:
                        continue

                filtered.append(r)

            if updated:
                session.commit()
            return filtered

    # ---------------------------------------------------------
    # ActionLog Operations
    # ---------------------------------------------------------

    def log_action(self, log_entry: ActionLog) -> None:
        """Stores an action log and updates parent session counters."""
        with self.get_session() as session:
            session.add(log_entry)

            # Update session action counters if parent session exists
            session_rec = session.get(SessionRecord, log_entry.session_id)
            if session_rec:
                session_rec.total_actions += 1
                if log_entry.status in ("REJECTED", "TIMED_OUT") or log_entry.risk_score >= 70:
                    session_rec.blocked_actions += 1
                session.add(session_rec)

            session.commit()

    def get_action(self, action_id: str) -> Optional[ActionLog]:
        """Retrieves an action log by its ID."""
        with self.get_session() as session:
            statement = select(ActionLog).where(ActionLog.id == action_id)
            return session.exec(statement).first()

    def update_action(self, log_entry: ActionLog) -> None:
        """Updates an existing action log (e.g. after approval or execution)."""
        with self.get_session() as session:
            session.merge(log_entry)
            session.commit()

    def list_actions(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> List[ActionLog]:
        """Lists action logs, optionally filtered by session_id."""
        with self.get_session() as session:
            statement = select(ActionLog)
            if session_id:
                statement = statement.where(ActionLog.session_id == session_id)
            statement = statement.order_by(ActionLog.timestamp.desc()).limit(limit)
            return list(session.exec(statement).all())

    def export_logs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Exports sanitized logs as JSON-serializable dictionaries."""
        actions = self.list_actions(session_id=session_id, limit=5000)
        exported = []
        for action in actions:
            data = {
                "id": action.id,
                "session_id": action.session_id,
                "timestamp": action.timestamp.isoformat(),
                "tool_name": action.tool_name,
                "raw_payload": action.raw_payload,
                "plain_language_explanation": action.plain_language_explanation,
                "language_code": action.language_code,
                "risk_score": action.risk_score,
                "risk_factors": json.loads(action.risk_factors) if action.risk_factors else [],
                "status": action.status,
                "user_decision_by": action.user_decision_by,
                "decision_notes": action.decision_notes,
                "execution_duration_ms": action.execution_duration_ms,
                "execution_result": action.execution_result,
            }
            exported.append(data)
        return exported

    # ---------------------------------------------------------
    # PolicyRule Operations
    # ---------------------------------------------------------

    def get_policy_rules(self, active_only: bool = True) -> List[PolicyRule]:
        """Lists configured policy rules."""
        with self.get_session() as session:
            statement = select(PolicyRule)
            if active_only:
                statement = statement.where(PolicyRule.is_active == True)
            return list(session.exec(statement).all())

    def add_policy_rule(self, rule: PolicyRule) -> PolicyRule:
        """Adds a new policy rule."""
        with self.get_session() as session:
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule

    def update_policy_rule(self, rule: PolicyRule) -> PolicyRule:
        """Updates an existing policy rule."""
        with self.get_session() as session:
            session.add(rule)
            session.commit()
            session.refresh(rule)
            return rule

    def delete_policy_rule(self, rule_id: str) -> bool:
        """Deletes a policy rule by ID."""
        with self.get_session() as session:
            rule = session.get(PolicyRule, rule_id)
            if not rule:
                return False
            session.delete(rule)
            session.commit()
            return True

    # ---------------------------------------------------------
    # ToolSetting Operations (Per-Tool & Generic Governance)
    # ---------------------------------------------------------

    def get_tool_settings(self) -> List[ToolSetting]:
        """Lists all per-tool and generic tool settings."""
        with self.get_session() as session:
            statement = select(ToolSetting).order_by(ToolSetting.tool_name.asc())
            return list(session.exec(statement).all())

    def get_tool_setting(self, tool_name: str) -> Optional[ToolSetting]:
        """Retrieves a setting entry by tool name."""
        with self.get_session() as session:
            statement = select(ToolSetting).where(ToolSetting.tool_name == tool_name)
            return session.exec(statement).first()

    def add_or_update_tool_setting(self, setting: ToolSetting) -> ToolSetting:
        """Upserts a per-tool or generic tool setting."""
        with self.get_session() as session:
            existing = session.exec(
                select(ToolSetting).where(ToolSetting.tool_name == setting.tool_name)
            ).first()
            if existing:
                existing.custom_threshold = setting.custom_threshold
                existing.downstream_url = setting.downstream_url
                existing.bypass_approval = setting.bypass_approval
                existing.timeout_ms = setting.timeout_ms
                existing.is_enabled = setting.is_enabled
                existing.description = setting.description
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return existing
            else:
                if not getattr(setting, "id", None):
                    setting.id = f"tool-{uuid.uuid4().hex[:8]}"
                session.add(setting)
                session.commit()
                session.refresh(setting)
                return setting

    def delete_tool_setting(self, setting_id: str) -> bool:
        """Deletes a tool setting by ID or tool name."""
        with self.get_session() as session:
            setting = session.get(ToolSetting, setting_id)
            if not setting:
                setting = session.exec(
                    select(ToolSetting).where(ToolSetting.tool_name == setting_id)
                ).first()
            if not setting:
                return False
            session.delete(setting)
            session.commit()
            return True

    # ---------------------------------------------------------
    # Storage Maintenance
    # ---------------------------------------------------------

    def prune_if_disk_low(
        self,
        min_free_mb: int = 500,
        threshold_score: int = 50,
        force: bool = False,
    ) -> int:
        """
        Prunes oldest low-risk (< threshold_score) auto-approved audit logs
        if local storage free space falls below min_free_mb or if force=True.
        Strictly preserves:
          - High-risk logs (risk_score >= threshold_score)
          - Blocked / rejected / timed-out logs (status in ['REJECTED', 'TIMED_OUT'])
          - Manual user decisions (user_decision_by == 'USER_MANUAL')
        Returns the count of deleted records.
        """
        if not force:
            try:
                total, used, free = shutil.disk_usage(Path(self.db_path).parent)
                free_mb = free // (1024 * 1024)
            except Exception:
                free_mb = min_free_mb + 1

            if free_mb >= min_free_mb:
                return 0

        with self.get_session() as session:
            # Query candidate low-risk logs for purging
            statement = (
                select(ActionLog)
                .where(ActionLog.risk_score < threshold_score)
                .where(ActionLog.status == "AUTO_APPROVED")
                .where(
                    (ActionLog.user_decision_by == None)
                    | (ActionLog.user_decision_by == "AUTO_POLICY")
                )
                .order_by(ActionLog.timestamp.asc())
                .limit(500)
            )
            low_risk_logs = list(session.exec(statement).all())
            deleted_count = len(low_risk_logs)
            for log in low_risk_logs:
                session.delete(log)
            session.commit()
            return deleted_count
