"""Human-in-the-Loop (HITL) connection holding and approval broker."""

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from backend.security.engine import SecurityAssessment


class DecisionStatus(str, Enum):
    """Lifecycle status of a tool invocation decision."""
    AUTO_APPROVED = "AUTO_APPROVED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"


class HITLBroker:
    """
    Suspends high-risk AI client connections via asyncio.Event,
    dispatches live approval requests to connected Web Panel clients,
    and resolves executions based on user manual decisions or timeouts.
    """

    def __init__(
        self,
        approval_threshold: int = 50,
        timeout_seconds: int = 90,
        ws_notifier: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
    ):
        self.approval_threshold = approval_threshold
        self.timeout_seconds = timeout_seconds
        self.ws_notifier = ws_notifier

        self._pending_events: Dict[str, asyncio.Event] = {}
        self._pending_data: Dict[str, Dict[str, Any]] = {}
        self._decisions: Dict[str, DecisionStatus] = {}
        self._decision_notes: Dict[str, str] = {}

    def set_threshold(self, threshold: int) -> None:
        """Dynamically updates approval threshold for hot-reloading."""
        self.approval_threshold = max(0, min(100, threshold))

    def set_timeout(self, seconds: int) -> None:
        """Dynamically updates timeout seconds for hot-reloading."""
        self.timeout_seconds = max(1, seconds)

    def set_ws_notifier(
        self, notifier: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        """Registers a websocket broadcast callback for live UI notification."""
        self.ws_notifier = notifier

    async def intercept_and_hold(
        self,
        action_id: str,
        session_id: str,
        tool_name: str,
        payload: Dict[str, Any],
        assessment: SecurityAssessment,
        plain_explanation: str,
        active_language: str = "en",
        timeout_seconds: Optional[int] = None,
    ) -> DecisionStatus:
        """
        Determines whether to auto-approve or suspend connection.
        If score >= threshold, blocks asynchronously until user decides or timeout expires.
        """
        # Req 4.1: If score < threshold, auto-approve immediately
        if assessment.risk_score < self.approval_threshold:
            self._decisions[action_id] = DecisionStatus.AUTO_APPROVED
            return DecisionStatus.AUTO_APPROVED

        # Req 4.2: If score >= threshold, suspend connection and emit approval event
        event = asyncio.Event()
        self._pending_events[action_id] = event
        self._decisions[action_id] = DecisionStatus.PENDING

        effective_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds

        approval_event = {
            "type": "PENDING_APPROVAL",
            "actionId": action_id,
            "sessionId": session_id,
            "toolName": tool_name,
            "riskScore": assessment.risk_score,
            "riskFactors": assessment.risk_factors,
            "plainExplanation": plain_explanation,
            "activeLanguage": active_language,
            "rawPayload": payload,
            "timeoutSeconds": effective_timeout,
            "receivedAt": time.time(),
        }
        self._pending_data[action_id] = approval_event

        # Emit instant WebSocket notification if notifier is wired
        if self.ws_notifier:
            try:
                res = self.ws_notifier(approval_event)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

        # Suspend connection until decision is submitted or timeout fires
        try:
            await asyncio.wait_for(event.wait(), timeout=float(effective_timeout))
            final_status = self._decisions.get(action_id, DecisionStatus.REJECTED)
            return final_status
        except asyncio.TimeoutError:
            # Req 4.5: Auto-reject upon expiration
            self._decisions[action_id] = DecisionStatus.TIMED_OUT
            return DecisionStatus.TIMED_OUT
        finally:
            self._pending_events.pop(action_id, None)
            self._pending_data.pop(action_id, None)

    async def submit_decision(
        self, action_id: str, decision: str, notes: Optional[str] = None
    ) -> bool:
        """
        Submits human approval or denial for a suspended action.
        Releases the held connection immediately.
        """
        decision_upper = decision.strip().upper()
        if action_id not in self._pending_events:
            return False

        if decision_upper in ("APPROVE", "APPROVED"):
            self._decisions[action_id] = DecisionStatus.APPROVED
        else:
            self._decisions[action_id] = DecisionStatus.REJECTED

        if notes:
            self._decision_notes[action_id] = notes

        event = self._pending_events[action_id]
        event.set()
        return True

    def get_hold_status(self, action_id: str) -> DecisionStatus:
        """Returns the current decision status for an action."""
        return self._decisions.get(action_id, DecisionStatus.PENDING)

    def get_decision_notes(self, action_id: str) -> Optional[str]:
        """Returns user notes associated with the decision."""
        return self._decision_notes.get(action_id)

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Returns snapshot list of currently pending approval requests."""
        return list(self._pending_data.values())
