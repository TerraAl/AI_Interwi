from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import DefaultDict, Dict, List

from fastapi import WebSocket


class WebsocketManager:
    """Tracks websocket connections per interview session."""

    def __init__(self) -> None:
        self._connections: DefaultDict[str, List[WebSocket]] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._locks[session_id]:
            self._connections[session_id].append(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(session_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(session_id, None)
            self._locks.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        connections = self._connections.get(session_id, [])
        if not connections:
            return
        dead: List[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

