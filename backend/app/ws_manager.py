"""Tiny WebSocket fan-out: every browser tab watching a session gets its live updates."""

from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id, websocket):
        await websocket.accept()
        if session_id not in self.connections:
            self.connections[session_id] = set()
        self.connections[session_id].add(websocket)

    def disconnect(self, session_id, websocket):
        if session_id in self.connections:
            self.connections[session_id].discard(websocket)
            if len(self.connections[session_id]) == 0:
                del self.connections[session_id]

    async def broadcast(self, session_id, message):
        dead = []
        for websocket in list(self.connections.get(session_id, [])):
            try:
                await websocket.send_json(message)
            except Exception:
                dead.append(websocket)
        for websocket in dead:
            self.disconnect(session_id, websocket)


manager = ConnectionManager()
