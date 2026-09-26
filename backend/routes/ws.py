"""WebSocket manager and routes for real-time Web Panel communication."""

import asyncio
import json
from typing import Any, Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.hitl.broker import HITLBroker


class ConnectionManager:
    """Manages active browser WebSocket connections to the Web Panel."""

    def __init__(self, hitl_broker: HITLBroker):
        self.hitl_broker = hitl_broker
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accepts and registers a new WebSocket client."""
        await websocket.accept()
        self.active_connections.add(websocket)

        # Immediately send current pending approvals to the connected client
        pending = self.hitl_broker.get_pending_approvals()
        for item in pending:
            await websocket.send_text(json.dumps(item))

    def disconnect(self, websocket: WebSocket) -> None:
        """Removes a disconnected client."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Broadcasts a JSON message to all connected clients."""
        payload = json.dumps(message)
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


def create_ws_router(manager: ConnectionManager, hitl_broker: HITLBroker) -> APIRouter:
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                data_text = await websocket.receive_text()
                try:
                    msg = json.loads(data_text)
                    msg_type = msg.get("type", "")
                    if msg_type in ("DECISION", "APPROVE", "DENY"):
                        action_id = msg.get("actionId")
                        decision = msg.get("decision") or msg_type
                        notes = msg.get("notes")
                        if action_id:
                            await hitl_broker.submit_decision(
                                action_id=action_id,
                                decision=decision,
                                notes=notes,
                            )
                            # Broadcast resolution to all panels
                            await manager.broadcast({
                                "type": "APPROVAL_RESOLVED",
                                "actionId": action_id,
                                "decision": decision,
                            })
                except Exception:
                    pass
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    return router
