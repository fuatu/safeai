"""Automated local chat session syncer for GitHub Copilot in VS Code.

Reads VS Code's internal chatSessions JSONL store directly from disk.
Requires ZERO external APIs, ZERO custom endpoints, and uses Copilot's
own subscription models (Gemini 3.8 Flash, GPT-4o, Claude) automatically.
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
        custom_title: Optional[str] = None

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

                    # Custom session title set by user or Copilot
                    if kind == 1 and k == ["customTitle"] and isinstance(v, str) and v.strip():
                        custom_title = v.strip()

                    # 1. Initial full state (kind 0)
                    if kind == 0 and isinstance(v, dict):
                        init_requests = v.get("requests", [])
                        for r in init_requests:
                            req_id = r.get("requestId")
                            if not req_id:
                                continue
                            msg = r.get("message", {}).get("text", "")
                            model = r.get("modelId", "copilot")
                            ts = r.get("timestamp", v.get("creationDate", int(time.time() * 1000)))
                            resp_parts = []
                            for resp in r.get("response", []):
                                if isinstance(resp, dict):
                                    val = resp.get("value")
                                    if isinstance(val, str) and val.strip() and not val.strip().startswith("**"):
                                        resp_parts.append(val)
                                elif isinstance(resp, str) and resp.strip():
                                    resp_parts.append(resp)
                            requests.append({
                                "id": req_id,
                                "prompt": msg,
                                "model": model,
                                "timestamp": ts,
                                "response_parts": resp_parts,
                                "tool_calls": [],
                            })

                    # 2. Incremental requests batch (kind 2, k == ["requests"])
                    elif kind == 2 and k == ["requests"] and isinstance(v, list):
                        for r in v:
                            req_id = r.get("requestId")
                            if not req_id:
                                continue
                            existing = next((x for x in requests if x["id"] == req_id), None)
                            if not existing:
                                msg = r.get("message", {}).get("text", "")
                                model = r.get("modelId", "copilot")
                                ts = r.get("timestamp", int(time.time() * 1000))
                                requests.append({
                                    "id": req_id,
                                    "prompt": msg,
                                    "model": model,
                                    "timestamp": ts,
                                    "response_parts": [],
                                    "tool_calls": [],
                                })

                    # 3. Incremental response chunks (kind 2, k == ["requests", idx, "response"])
                    elif kind == 2 and isinstance(k, list) and len(k) == 3 and k[0] == "requests" and k[2] == "response" and isinstance(v, list):
                        idx = k[1]
                        if isinstance(idx, int) and 0 <= idx < len(requests):
                            for part in v:
                                if isinstance(part, dict):
                                    if part.get("kind") == "toolInvocationSerialized":
                                        tool_id = part.get("toolId")
                                        tool_call_id = part.get("toolCallId")
                                        tool_spec = part.get("toolSpecificData", {})
                                        cmd = None
                                        if isinstance(tool_spec, dict):
                                            cmd_line = tool_spec.get("commandLine")
                                            if isinstance(cmd_line, dict):
                                                cmd = cmd_line.get("original") or cmd_line.get("toolEdited")
                                            elif isinstance(cmd_line, str):
                                                cmd = cmd_line
                                            if not cmd and "confirmation" in tool_spec and isinstance(tool_spec["confirmation"], dict):
                                                cmd = tool_spec["confirmation"].get("commandLine")
                                            if not cmd and "rawInput" in tool_spec and isinstance(tool_spec["rawInput"], dict):
                                                cmd = tool_spec["rawInput"].get("command")

                                        if tool_id:
                                            existing_tc = next((tc for tc in requests[idx]["tool_calls"] if tc.get("id") == tool_call_id), None)
                                            if not existing_tc:
                                                requests[idx]["tool_calls"].append({
                                                    "name": tool_id,
                                                    "id": tool_call_id,
                                                    "arguments": {"command": cmd} if cmd else {},
                                                    "output": "",
                                                })
                                            elif cmd and not existing_tc.get("arguments", {}).get("command"):
                                                existing_tc["arguments"] = {"command": cmd}
                                    else:
                                        val = part.get("value")
                                        if isinstance(val, str) and val.strip() and not val.strip().startswith("**"):
                                            requests[idx]["response_parts"].append(val)
                                elif isinstance(part, str) and part.strip():
                                    requests[idx]["response_parts"].append(part)

                    # 4. Result metadata with complete toolCallRounds and responses (kind 1, k == ["requests", idx, "result"])
                    elif kind == 1 and isinstance(k, list) and len(k) == 3 and k[0] == "requests" and k[2] == "result" and isinstance(v, dict):
                        idx = k[1]
                        if isinstance(idx, int) and 0 <= idx < len(requests):
                            rounds = v.get("metadata", {}).get("toolCallRounds", [])
                            results = v.get("metadata", {}).get("toolCallResults", {})
                            for r in rounds:
                                resp_val = r.get("response")
                                if isinstance(resp_val, str) and resp_val.strip():
                                    requests[idx]["response_parts"].append(resp_val.strip())
                                for tc in r.get("toolCalls", []):
                                    cid = tc.get("id")
                                    raw_args = tc.get("arguments", "")
                                    args = json.loads(raw_args) if isinstance(raw_args, str) and raw_args.strip().startswith("{") else raw_args
                                    out_val = ""
                                    res_obj = results.get(cid, {})
                                    if isinstance(res_obj.get("content"), list):
                                        for c in res_obj["content"]:
                                            if isinstance(c, dict) and isinstance(c.get("value"), str):
                                                out_val += c["value"]

                                    # Update or append
                                    existing_tc = next((t for t in requests[idx]["tool_calls"] if t.get("id") == cid or (cid and str(cid).startswith(str(t.get("id", "none"))))), None)
                                    if existing_tc:
                                        if args:
                                            existing_tc["arguments"] = args
                                        if out_val:
                                            existing_tc["output"] = out_val
                                    else:
                                        requests[idx]["tool_calls"].append({
                                            "name": tc.get("name"),
                                            "id": cid,
                                            "arguments": args,
                                            "output": out_val,
                                        })
        except Exception:
            return []

        # Consolidate responses
        results = []
        for r in requests:
            cleaned_parts = []
            for p in r["response_parts"]:
                if p not in cleaned_parts:
                    cleaned_parts.append(p)
            resp_text = "\n\n".join(cleaned_parts).strip()

            results.append({
                "id": r["id"],
                "prompt": r["prompt"],
                "response": resp_text,
                "model": r["model"],
                "timestamp": r["timestamp"],
                "custom_title": custom_title,
                "tool_calls": r.get("tool_calls", []),
            })

        return results

    def sync_files(self, chat_files: List[Path]) -> int:
        """Imports conversation turns from the specified chat session files."""
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

            # Determine title: prioritize custom_title, then prompt snippet
            custom_title = turns[0].get("custom_title") if turns else None
            if custom_title:
                formatted_title = f'VS Code + Copilot: "{custom_title}" ({date_str})'
            else:
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
                # Update title if it was generic, missing prompt/title, or placeholder
                if not target_session.title or "Connected" in target_session.title or target_session.title.startswith("AI Client") or '"Copilot Chat"' in target_session.title:
                    target_session.title = formatted_title
                    target_session.client_name = "VS Code + GitHub Copilot"
                    self.audit_store.update_session(target_session)

            for t in turns:
                req_id = t["id"]
                action_id = f"copilot-{req_id}"

                prompt = t["prompt"]
                response = t["response"]
                model = t["model"]
                ts_ms = t["timestamp"]
                created_at = (
                    datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
                    if ts_ms
                    else datetime.now(timezone.utc)
                )

                # Note: Conversational chat turn logging is disabled.
                # Only tool invocations (MCP and terminal commands) are tracked.

                # 2. Sync any tool calls (e.g. run_in_terminal commands) that bypassed MCP
                tool_calls = t.get("tool_calls", [])
                for tc in tool_calls:
                    tc_name = tc.get("name") or tc.get("tool_id")
                    if tc_name in ("run_in_terminal", "terminal"):
                        # Extract command
                        raw_args = tc.get("arguments", {})
                        if isinstance(raw_args, dict):
                            cmd = raw_args.get("command") or raw_args.get("commandLine")
                            explanation_note = raw_args.get("explanation") or raw_args.get("goal")
                        else:
                            cmd = str(raw_args)
                            explanation_note = None

                        if not cmd or not cmd.strip():
                            continue

                        cmd = cmd.strip()
                        tc_id = tc.get("id") or uuid.uuid4().hex[:12]
                        clean_tc_id = tc_id.replace("call_", "").replace("__vscode-", "-")[:22]
                        term_action_id = f"term-{clean_tc_id}"

                        if term_action_id in self._synced_request_ids:
                            continue
                        if self.audit_store.get_action(term_action_id):
                            self._synced_request_ids.add(term_action_id)
                            continue

                        # Evaluate security & risk
                        assessment = self.security_engine.evaluate_payload("bash", {"command": cmd})
                        plain_explanation = self.explainer_engine.generate_explanation(
                            tool_name="bash",
                            payload={"command": cmd},
                            assessment=assessment,
                        )

                        # Sanitize output
                        output = tc.get("output", "")
                        sanitized_output = self.dlp_masker.redact_payload({"text": output}).get("text", output) if output else "Executed directly in host terminal."

                        term_payload = {
                            "command": cmd,
                            "source": "vscode_run_in_terminal",
                            "tool_call_id": tc_id,
                            "explanation": explanation_note,
                        }

                        term_action = ActionLog(
                            id=term_action_id,
                            session_id=target_session.id,
                            timestamp=created_at,
                            tool_name="bash",
                            raw_payload=json.dumps(term_payload, ensure_ascii=False),
                            plain_language_explanation=f"{plain_explanation} (VS Code Terminal)",
                            language_code="en",
                            risk_score=assessment.risk_score,
                            risk_factors=json.dumps(assessment.risk_factors),
                            status="AUTO_APPROVED",
                            user_decision_by="HOST_TERMINAL",
                            execution_result=sanitized_output,
                        )
                        self.audit_store.log_action(term_action)
                        self._synced_request_ids.add(term_action_id)
                        synced_count += 1

                        self._broadcast_action(
                            action_id=term_action_id,
                            session_id=target_session.id,
                            tool_name="bash",
                            risk_score=assessment.risk_score,
                            explanation=term_action.plain_language_explanation,
                            execution_result=sanitized_output,
                        )

        return synced_count

    def sync_all(self, max_files: int = 50) -> int:
        """
        Scans recent VS Code Copilot chat files and imports any unlogged turns
        into SafeAI's persistent audit store, organizing each into a clearly
        named session with user prompt snippet, model, and date.
        """
        chat_files = self.find_all_chat_session_files(max_files=max_files)
        synced = self.sync_files(chat_files)
        for f in chat_files:
            try:
                self._file_mtimes[str(f)] = f.stat().st_mtime
            except Exception:
                pass
        return synced

    def sync_recent(self, max_files: int = 50) -> int:
        """
        Scans recent VS Code Copilot chat files and synchronizes any file whose mtime changed.
        Works across all sessions (including older sessions that receive new activities).
        """
        chat_files = self.find_all_chat_session_files(max_files=max_files)
        files_to_sync = []
        for f in chat_files:
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
        """Syncs all recently active chat files across any session."""
        return self.sync_recent(max_files=50)
