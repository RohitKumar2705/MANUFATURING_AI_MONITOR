"""Broadcasts realtime JSON messages (worker updates, alerts, camera status,
process updates) to every connected dashboard WebSocket client."""
from __future__ import annotations
import asyncio
import json
from fastapi import WebSocket
from app.core.logging_setup import logger


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def _broadcast_async(self, message: dict):
        dead = []
        payload = json.dumps(message, default=str)
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for d in dead:
            self.disconnect(d)

    def broadcast(self, message: dict):
        """Thread-safe entry point: camera worker threads call this directly."""
        if self._loop is None or not self.active:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast_async(message), self._loop)
        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {e}")


connection_manager = ConnectionManager()
