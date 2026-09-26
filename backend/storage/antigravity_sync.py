"""Automated local chat session syncer for Google Antigravity IDE.

Reads Antigravity's internal transcript JSONL logs directly from disk.
Requires ZERO external APIs, ZERO custom endpoints, and uses Antigravity's
local transcript files automatically.
"""

import asyncio
import glob
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.explainer.engine import ExplainerEngine
from backend.models.schemas import ActionLog, SessionRecord
from backend.security.dlp import DLPMasker
from backend.security.engine import SecurityEngine
from backend.storage.audit_store import AuditStore


class AntigravityChatSyncer:
    """Watches and imports Google Antigravity conversation transcripts automatically."""

    def __init__(
        self,
        audit_store: AuditStore,
        dlp_masker: Optional[DLPMasker] = None,
        ws_broadcast: Optional[Callable[[Dict[str, Any]], Any]] = None,
        custom_storage_dir: Optional[str] = None,
    ):
        self.audit_store = audit_store
        self.dlp_masker = dlp_masker or DLPMasker()
        self.security_engine = SecurityEngine()
        self.explainer_engine = ExplainerEngine()
        self.ws_broadcast = ws_broadcast
        self.custom_storage_dir = custom_storage_dir
        self._last_processed_mtime: float = 0
        self._synced_request_ids: set = set()
        self._file_mtimes: Dict[str, float] = {}

    def _broadcast_action(
        self,
        action_id: str,
        session_id: str,
        tool_name: str,
        risk_score: int,
        explanation: str,
        execution_result: str,
    ) -> None:
        """Broadcasts an ACTION_LOGGED notification over WebSocket."""
        if not self.ws_broadcast:
            return
        msg = {
            "type": "ACTION_LOGGED",
            "actionId": action_id,
            "sessionId": session_id,
            "toolName": tool_name,
            "status": "AUTO_APPROVED",
            "riskScore": risk_score,
            "explanation": explanation,
            "executionResult": execution_result,
        }
        try:
            res = self.ws_broadcast(msg)
            if asyncio.iscoroutine(res):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(res)
                except RuntimeError:
                    pass
        except Exception:
            pass

    def find_brain_dirs(self) -> List[Path]:
        """Locates Antigravity brain storage directories across container and host."""
        if self.custom_storage_dir and Path(self.custom_storage_dir).exists():
            return [Path(self.custom_storage_dir)]

        candidates = []

        # 1. Docker mounted volume path
        docker_path = Path("/antigravity_brain")
        if docker_path.exists() and docker_path.is_dir():
            candidates.append(docker_path)

        # 2. Host standard path (~/.gemini/antigravity-ide/brain)
        home = Path.home()
        host_path = home / ".gemini" / "antigravity-ide" / "brain"
        if host_path.exists() and host_path.is_dir():
            candidates.append(host_path)

        return candidates

    def find_all_transcript_files(self, max_files: int = 25) -> List[Path]:
        """Finds recent transcript.jsonl files sorted by modification time descending."""
        brain_dirs = self.find_brain_dirs()
        all_files: List[tuple[float, Path]] = []

        for bdir in brain_dirs:
            pattern = str(bdir / "*" / ".system_generated" / "logs" / "transcript.jsonl")
            for fpath in glob.glob(pattern):
                try:
                    p = Path(fpath)
                    if p.is_file() and p.stat().st_size > 0:
                        all_files.append((p.stat().st_mtime, p))
                except Exception:
                    continue

        all_files.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in all_files[:max_files]]

    def get_latest_transcript_file(self) -> Optional[Path]:
        """Finds the single most recently modified transcript.jsonl file."""
        files = self.find_all_transcript_files(max_files=1)
        return files[0] if files else None

    def parse_transcript_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parses Antigravity transcript.jsonl into structured conversation turns."""
        turns: List[Dict[str, Any]] = []
        cur_turn: Optional[Dict[str, Any]] = None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue

                    stype = item.get("type")
                    source = item.get("source")
                    sidx = item.get("step_index")
                    ca = item.get("created_at")

                    if stype == "USER_INPUT" and source == "USER_EXPLICIT":
                        if cur_turn:
                            turns.append(cur_turn)
                        raw_c = item.get("content", "")
                        if "<USER_REQUEST>" in raw_c:
                            prompt = raw_c.split("<USER_REQUEST>")[1].split("</USER_REQUEST>")[0].strip()
                        else:
                            prompt = raw_c.split("<ADDITIONAL_METADATA>")[0].strip()

                        cur_turn = {
                            "step_index": sidx,
                            "id": f"step-{sidx}",
                            "prompt": prompt,
                            "created_at": ca,
                            "response_parts": [],
                            "tool_calls": [],
                        }
                    elif cur_turn:
                        if stype == "PLANNER_RESPONSE" and source == "MODEL":
                            c = item.get("content", "").strip()
                            if c:
                                cur_turn["response_parts"].append(c)
                            for tc in item.get("tool_calls", []):
                                tname = tc.get("name") or tc.get("function", {}).get("name")
                                targs = tc.get("args") or tc.get("arguments") or {}
                                cur_turn["tool_calls"].append({
                                    "name": tname,
                                    "args": targs,
                                    "step_index": sidx,
                                    "created_at": ca,
                                    "output": "",
                                })
                        elif source == "MODEL" and item.get("content") and cur_turn["tool_calls"]:
                            cur_turn["tool_calls"][-1]["output"] = item.get("content", "")

            if cur_turn:
                turns.append(cur_turn)
        except Exception:
            return []

        # Consolidate responses
        results = []
        for t in turns:
            cleaned_parts = []
            for p in t["response_parts"]:
                if p not in cleaned_parts:
                    cleaned_parts.append(p)
            resp_text = "\n\n".join(cleaned_parts).strip()
            results.append({
                "step_index": t["step_index"],
                "id": t["id"],
                "prompt": t["prompt"],
                "response": resp_text,
                "created_at": t.get("created_at"),
                "tool_calls": t.get("tool_calls", []),
            })

        return results

    def sync_files(self, transcript_files: List[Path]) -> int:
        """Imports Antigravity conversation turns and executed tools into SafeAI audit store."""
        if not transcript_files:
            return 0

        synced_count = 0

        for file_path in transcript_files:
            turns = self.parse_transcript_file(file_path)
            if not turns:
                continue

            conv_id = file_path.parent.parent.parent.name
            session_stem = conv_id[:18]
            session_id = f"antigravity-{session_stem}"

            # Calculate session date from first turn or file mtime
            first_ca = turns[0].get("created_at") if turns else None
            if first_ca:
                try:
                    session_date = datetime.fromisoformat(first_ca.replace("Z", "+00:00"))
                except Exception:
                    session_date = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            else:
                session_date = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

            date_str = session_date.strftime("%b %d, %H:%M")
            first_prompt = turns[0]["prompt"].strip().replace("\n", " ") if turns else ""
            if len(first_prompt) > 34:
                prompt_snippet = first_prompt[:34] + "..."
            else:
                prompt_snippet = first_prompt or "Conversation"
            formatted_title = f'Antigravity: "{prompt_snippet}" ({date_str})'

            # Get or create target session
            target_session = self.audit_store.get_session_by_id(session_id)
            if not target_session:
                target_session = SessionRecord(
                    id=session_id,
                    client_name="Google Antigravity IDE",
                    title=formatted_title,
                    started_at=session_date,
                )
                self.audit_store.create_session(target_session)
            else:
                if not target_session.title or target_session.title.startswith("AI Client"):
                    target_session.title = formatted_title
                    target_session.client_name = "Google Antigravity IDE"
                    self.audit_store.update_session(target_session)

            for t in turns:
                sidx = t["step_index"]
                action_id = f"antigravity-{session_stem[:8]}-turn-{sidx}"

                prompt = t["prompt"]
                response = t["response"]
                turn_ca = t.get("created_at")
                if turn_ca:
                    try:
                        created_at = datetime.fromisoformat(turn_ca.replace("Z", "+00:00"))
                    except Exception:
                        created_at = session_date
                else:
                    created_at = session_date

                # Note: Conversational chat turn logging is disabled.
                # Only tool invocations (run_command, file edits, etc.) are tracked.

                # 2. Sync audited tool calls executed in this turn
                for tc_idx, tc in enumerate(t.get("tool_calls", [])):
                    tc_name = tc.get("name")
                    tc_args = tc.get("args") or {}

                    if tc_name == "run_command":
                        cmd = tc_args.get("CommandLine") or tc_args.get("command") or ""
                        if isinstance(cmd, str):
                            cmd = cmd.strip()
                            if (cmd.startswith('"') and cmd.endswith('"')) or (cmd.startswith("'") and cmd.endswith("'")):
                                cmd = cmd[1:-1]
                        if not cmd:
                            continue

                        tool_action_id = f"antigravity-cmd-{sidx}-{tc_idx}"
                        if tool_action_id in self._synced_request_ids:
                            continue
                        if self.audit_store.get_action(tool_action_id):
                            self._synced_request_ids.add(tool_action_id)
                            continue

                        assessment = self.security_engine.evaluate_payload("bash", {"command": cmd})
                        plain_explanation = self.explainer_engine.generate_explanation(
                            tool_name="bash",
                            payload={"command": cmd},
                            assessment=assessment,
                        )

                        output = tc.get("output", "")
                        sanitized_output = self.dlp_masker.redact_payload({"text": output}).get("text", output) if output else "Executed by Antigravity."

                        cmd_payload = {
                            "command": cmd,
                            "cwd": tc_args.get("Cwd", ""),
                            "source": "antigravity_run_command",
                            "toolAction": tc_args.get("toolAction", ""),
                            "toolSummary": tc_args.get("toolSummary", ""),
                        }

                        action_entry = ActionLog(
                            id=tool_action_id,
                            session_id=target_session.id,
                            timestamp=created_at,
                            tool_name="bash",
                            raw_payload=json.dumps(cmd_payload, ensure_ascii=False),
                            plain_language_explanation=f"{plain_explanation} (Antigravity)",
                            language_code="en",
                            risk_score=assessment.risk_score,
                            risk_factors=json.dumps(assessment.risk_factors),
                            status="AUTO_APPROVED",
                            user_decision_by="ANTIGRAVITY_AGENT",
                            execution_result=sanitized_output,
                        )
                        self.audit_store.log_action(action_entry)
                        self._synced_request_ids.add(tool_action_id)
                        synced_count += 1
                        self._broadcast_action(
                            action_id=tool_action_id,
                            session_id=target_session.id,
                            tool_name="bash",
                            risk_score=assessment.risk_score,
                            explanation=action_entry.plain_language_explanation,
                            execution_result=sanitized_output,
                        )

                    elif tc_name in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
                        target_file = tc_args.get("TargetFile") or tc_args.get("file_path") or ""
                        if isinstance(target_file, str):
                            target_file = target_file.strip()
                            if (target_file.startswith('"') and target_file.endswith('"')) or (target_file.startswith("'") and target_file.endswith("'")):
                                target_file = target_file[1:-1]
                        if not target_file:
                            continue

                        tool_action_id = f"antigravity-file-{sidx}-{tc_idx}"
                        if tool_action_id in self._synced_request_ids:
                            continue
                        if self.audit_store.get_action(tool_action_id):
                            self._synced_request_ids.add(tool_action_id)
                            continue

                        assessment = self.security_engine.evaluate_payload("write_file", {"TargetFile": target_file})
                        plain_explanation = self.explainer_engine.generate_explanation(
                            tool_name="write_file",
                            payload={"TargetFile": target_file},
                            assessment=assessment,
                        )

                        output = tc.get("output", "")
                        sanitized_output = self.dlp_masker.redact_payload({"text": output}).get("text", output) if output else "File updated by Antigravity."

                        file_payload = {
                            "TargetFile": target_file,
                            "source": f"antigravity_{tc_name}",
                            "description": tc_args.get("Description", ""),
                        }

                        action_entry = ActionLog(
                            id=tool_action_id,
                            session_id=target_session.id,
                            timestamp=created_at,
                            tool_name="write_file",
                            raw_payload=json.dumps(file_payload, ensure_ascii=False),
                            plain_language_explanation=f"{plain_explanation} (Antigravity)",
                            language_code="en",
                            risk_score=assessment.risk_score,
                            risk_factors=json.dumps(assessment.risk_factors),
                            status="AUTO_APPROVED",
                            user_decision_by="ANTIGRAVITY_AGENT",
                            execution_result=sanitized_output,
                        )
                        self.audit_store.log_action(action_entry)
                        self._synced_request_ids.add(tool_action_id)
                        synced_count += 1
                        self._broadcast_action(
                            action_id=tool_action_id,
                            session_id=target_session.id,
                            tool_name="write_file",
                            risk_score=assessment.risk_score,
                            explanation=action_entry.plain_language_explanation,
                            execution_result=sanitized_output,
                        )

        return synced_count

    def sync_all(self, max_files: int = 50) -> int:
        """Scans recent Antigravity transcripts and imports them into SafeAI audit store."""
        transcript_files = self.find_all_transcript_files(max_files=max_files)
        synced = self.sync_files(transcript_files)
        for f in transcript_files:
            try:
                self._file_mtimes[str(f)] = f.stat().st_mtime
            except Exception:
                pass
        return synced

    def sync_recent(self, max_files: int = 50) -> int:
        """
        Scans recent Antigravity transcripts and synchronizes any file whose mtime changed.
        Works across all sessions (including older sessions that receive new activities).
        """
        transcript_files = self.find_all_transcript_files(max_files=max_files)
        files_to_sync = []
        for f in transcript_files:
            try:
                mtime = f.stat().st_mtime
                if mtime > self._file_mtimes.get(str(f), 0):
                    files_to_sync.append(f)
            except Exception:
                continue

        if not files_to_sync:
            return 0

        synced = self.sync_files(files_to_sync)
        for f in files_to_sync:
            try:
                self._file_mtimes[str(f)] = f.stat().st_mtime
            except Exception:
                pass
        return synced

    def sync_latest(self) -> int:
        """Syncs all recently active transcript files across any session."""
        return self.sync_recent(max_files=50)
