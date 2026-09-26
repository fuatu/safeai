"""Automated local chat session syncer for GitHub Copilot in VS Code.

Reads VS Code's internal chatSessions JSONL store directly from disk.
Requires ZERO external APIs, ZERO custom endpoints, and uses Copilot's
own subscription models (Gemini 3.8 Flash, GPT-4o, Claude) automatically.
"""

import glob
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.models.schemas import ActionLog, SessionRecord
from backend.security.dlp import DLPMasker
from backend.storage.audit_store import AuditStore


class CopilotChatSyncer:
    """Watches and imports VS Code GitHub Copilot chat history automatically."""

    def __init__(
        self,
        audit_store: AuditStore,
        dlp_masker: Optional[DLPMasker] = None,
        ws_broadcast: Optional[Callable[[Dict[str, Any]], Any]] = None,
        custom_storage_dir: Optional[str] = None,
    ):
        self.audit_store = audit_store
        self.dlp_masker = dlp_masker or DLPMasker()
        self.ws_broadcast = ws_broadcast
        self.custom_storage_dir = custom_storage_dir
        self._last_processed_mtime: float = 0
        self._synced_request_ids: set = set()

    def find_workspace_storage_dirs(self) -> List[Path]:
        """Locates VS Code workspaceStorage directories across OS platforms."""
        if self.custom_storage_dir and Path(self.custom_storage_dir).exists():
            return [Path(self.custom_storage_dir)]

        candidates = []

        # 1. Docker mounted volume path
        docker_path = Path("/vscode_storage")
        if docker_path.exists() and docker_path.is_dir():
            candidates.append(docker_path)

        # 2. Host OS standard paths
        home = Path.home()
        # macOS
        mac_path = home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"
        if mac_path.exists():
            candidates.append(mac_path)

        # Linux
        linux_path = home / ".config" / "Code" / "User" / "workspaceStorage"
        if linux_path.exists():
            candidates.append(linux_path)

        # Windows
        appdata = os.environ.get("APPDATA")
        if appdata:
            win_path = Path(appdata) / "Code" / "User" / "workspaceStorage"
            if win_path.exists():
                candidates.append(win_path)

        return candidates

    def find_all_chat_session_files(self, max_files: int = 20) -> List[Path]:
        """Finds recent chatSessions/*.jsonl files sorted by modification time descending."""
        storage_dirs = self.find_workspace_storage_dirs()
        all_files: List[tuple[float, Path]] = []

        for sdir in storage_dirs:
            pattern = str(sdir / "*" / "chatSessions" / "*.jsonl")
            for fpath in glob.glob(pattern):
                try:
                    p = Path(fpath)
                    if p.is_file() and p.stat().st_size > 0:
                        all_files.append((p.stat().st_mtime, p))
                except Exception:
                    continue

        # Sort by newest first
        all_files.sort(key=lambda x: x[0], reverse=True)
        return [f[1] for f in all_files[:max_files]]

    def get_latest_chat_session_file(self) -> Optional[Path]:
        """Finds the most recently modified chatSessions/*.jsonl file."""
        files = self.find_all_chat_session_files(max_files=1)
        return files[0] if files else None

    def parse_chat_session_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parses VS Code incremental JSONL chat session log into structured conversation turns."""
        requests: List[Dict[str, Any]] = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        item = json.loads(line)
                    except Exception:
                        continue
                    kind = item.get("kind")
                    k = item.get("k", [])
                    v = item.get("v")

                    # New requests batch
                    if kind == 2 and k == ["requests"] and isinstance(v, list):
                        for r in v:
                            req_id = r.get("requestId")
                            if not req_id:
                                continue
                            msg = r.get("message", {}).get("text", "")
                            model = r.get("modelId", "copilot")
                            ts = r.get("timestamp", int(time.time() * 1000))

                            existing = next((x for x in requests if x["id"] == req_id), None)
                            if not existing:
                                requests.append({
                                    "id": req_id,
                                    "prompt": msg,
                                    "model": model,
                                    "timestamp": ts,
                                    "response_parts": [],
                                })

                    # Incremental response chunks
                    elif kind == 2 and len(k) == 3 and k[0] == "requests" and k[2] == "response" and isinstance(v, list):
                        idx = k[1]
                        if isinstance(idx, int) and 0 <= idx < len(requests):
                            for part in v:
                                if isinstance(part, dict) and "value" in part and part["value"]:
                                    requests[idx]["response_parts"].append(part["value"])
        except Exception:
            return []

        # Consolidate responses
        results = []
        for r in requests:
            resp_text = ""
            for p in r["response_parts"]:
                # Filter out pure internal reasoning markers if final text exists
                if not p.startswith("**Analyzing") and not p.startswith("**Exploring"):
                    resp_text = p
            if not resp_text and r["response_parts"]:
                resp_text = r["response_parts"][-1]

            results.append({
                "id": r["id"],
                "prompt": r["prompt"],
                "response": resp_text.strip(),
                "model": r["model"],
                "timestamp": r["timestamp"],
            })

        return results

    def sync_all(self, max_files: int = 15) -> int:
        """
        Scans recent VS Code Copilot chat files and imports any unlogged turns
        into SafeAI's persistent audit store, organizing each into a clearly
        named session with user prompt snippet, model, and date.
        """
        chat_files = self.find_all_chat_session_files(max_files=max_files)
        if not chat_files:
            return 0

        synced_count = 0

        for file_path in chat_files:
            turns = self.parse_chat_session_file(file_path)
            if not turns:
                continue

            session_stem = file_path.stem[:18]
            session_id = f"copilot-{session_stem}"

            # Calculate session date from first turn or file mtime
            first_ts_ms = turns[0]["timestamp"] if turns[0].get("timestamp") else None
            if first_ts_ms:
                session_date = datetime.fromtimestamp(first_ts_ms / 1000.0, tz=timezone.utc)
            else:
                session_date = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)

            date_str = session_date.strftime("%b %d, %H:%M")

            # Determine title from first meaningful prompt
            first_prompt = turns[0]["prompt"].strip().replace("\n", " ") if turns else ""
            if len(first_prompt) > 34:
                prompt_snippet = first_prompt[:34] + "..."
            else:
                prompt_snippet = first_prompt or "Conversation"

            formatted_title = f'VS Code + Copilot: "{prompt_snippet}" ({date_str})'

            # Get or create target session
            target_session = self.audit_store.get_session_by_id(session_id)
            if not target_session:
                target_session = SessionRecord(
                    id=session_id,
                    client_name="VS Code + GitHub Copilot",
                    title=formatted_title,
                    started_at=session_date,
                )
                self.audit_store.create_session(target_session)
            else:
                # Update title if it was generic or missing date
                if not target_session.title or "Connected" in target_session.title or date_str not in target_session.title:
                    target_session.title = formatted_title
                    target_session.client_name = "VS Code + GitHub Copilot"
                    self.audit_store.update_session(target_session)

            for t in turns:
                req_id = t["id"]
                action_id = f"copilot-{req_id}"

                # Check if already logged
                if action_id in self._synced_request_ids:
                    continue
                if self.audit_store.get_action(action_id):
                    self._synced_request_ids.add(action_id)
                    continue

                prompt = t["prompt"]
                response = t["response"]
                model = t["model"]
                ts_ms = t["timestamp"]
                created_at = (
                    datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                    if ts_ms
                    else datetime.now(timezone.utc)
                )

                # DLP redact
                sanitized_prompt = self.dlp_masker.redact_payload({"text": prompt}).get("text", prompt)
                sanitized_resp = self.dlp_masker.redact_payload({"text": response}).get("text", response)

                payload_data = {
                    "prompt": sanitized_prompt,
                    "response": sanitized_resp,
                    "model": model,
                    "source": "vscode_copilot_chat",
                }

                clean_turn_p = sanitized_prompt.strip().replace("\n", " ")
                short_prompt = (clean_turn_p[:50] + "...") if len(clean_turn_p) > 50 else clean_turn_p
                model_short = model.replace("copilot/", "")

                log_entry = ActionLog(
                    id=action_id,
                    session_id=target_session.id,
                    timestamp=created_at,
                    tool_name="copilot_chat",
                    raw_payload=json.dumps(payload_data, ensure_ascii=False),
                    plain_language_explanation=f'Copilot Chat ({model_short}): "{short_prompt}"',
                    language_code="en",
                    risk_score=5,
                    risk_factors=json.dumps(["CONVERSATION_HISTORY"]),
                    status="AUTO_APPROVED",
                    user_decision_by="AUTO_POLICY",
                    execution_result=sanitized_resp or "Response processed by Copilot.",
                )
                self.audit_store.log_action(log_entry)
                self._synced_request_ids.add(action_id)
                synced_count += 1

                # Broadcast live update
                if self.ws_broadcast:
                    try:
                        self.ws_broadcast({
                            "type": "ACTION_LOGGED",
                            "actionId": action_id,
                            "sessionId": target_session.id,
                            "toolName": "copilot_chat",
                            "status": "AUTO_APPROVED",
                            "riskScore": 5,
                            "explanation": log_entry.plain_language_explanation,
                        })
                    except Exception:
                        pass

        return synced_count

    def sync_latest(self) -> int:
        """Alias to sync_all for background polling and immediate sync."""
        return self.sync_all(max_files=15)
