"""
VERISYNTH V-SOC — WebSocket Manager

Manages all WebSocket client connections and broadcasts events.

Responsibilities:
  - Accept and track WebSocket connections
  - Replay recent event history to newly-connected clients
    so the dashboard is immediately populated on connect
  - Broadcast every new event to all connected clients
  - Handle disconnects cleanly — remove dead connections
  - Send keepalive PINGs to detect stale connections

Connection lifecycle:
  1. Client connects → accept → send history replay → subscribe to bus
  2. Bus pushes event → broadcast to all live clients
  3. Client disconnects → unsubscribe from bus → remove from pool
  4. No event for 15s → send PING → client must respond or be dropped
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

from server.event_bus import bus, Event, PING

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Tracks all active WebSocket connections.
    Each connection gets its own bus subscriber queue.
    """

    def __init__(self) -> None:
        # ws → subscriber queue
        self._connections: Dict[WebSocket, asyncio.Queue] = {}
        self._connect_times: Dict[WebSocket, float] = {}
        self._message_counts: Dict[WebSocket, int] = {}

        logger.info("ConnectionManager created")

    async def connect(self, ws: WebSocket) -> asyncio.Queue:
        """
        Accept a new WebSocket connection and register it.
        Returns the subscriber queue for this connection.
        """
        await ws.accept()
        q = bus.subscribe()
        self._connections[ws]     = q
        self._connect_times[ws]   = time.time()
        self._message_counts[ws]  = 0

        logger.info(
            "WS client connected | total=%d remote=%s",
            len(self._connections),
            getattr(ws, 'client', 'unknown'),
        )
        return q

    def disconnect(self, ws: WebSocket) -> None:
        """Remove a connection and unsubscribe from the bus."""
        q = self._connections.pop(ws, None)
        self._connect_times.pop(ws, None)
        self._message_counts.pop(ws, None)

        if q is not None:
            bus.unsubscribe(q)

        logger.info(
            "WS client disconnected | remaining=%d",
            len(self._connections),
        )

    async def send_history(self, ws: WebSocket, n: int = 100) -> None:
        """
        Send recent event history to a newly-connected client.
        This populates the dashboard immediately without waiting
        for the simulation to emit new events.
        """
        history = bus.get_history(n=n)
        sent = 0
        for event in history:
            try:
                await ws.send_text(event.to_json())
                sent += 1
            except Exception:
                break
        logger.debug("WS history replay | sent=%d events", sent)

    async def broadcast(self, message: str) -> None:
        """
        Send a raw message string to all connected clients.

        NOTE: Normal simulation events are NOT delivered via this method.
        They flow through each client's individual bus subscriber queue
        (see websocket_endpoint). This method is reserved for
        administrative notifications only — e.g. server shutdown warnings,
        maintenance mode alerts, or debug broadcasts.

        Future: support incremental replay via event seq numbers so
        reconnecting clients only request events they missed:
            client sends: {"type": "REPLAY_FROM", "seq": 1042}
            server sends: all bus.history events with seq > 1042
        This requires client-side seq tracking, which the event_id + seq
        fields on every Event already support.

        Future: replace application-level PING with native WebSocket
        ping/pong frames (ws.send_bytes / ping frame) for more reliable
        stale connection detection at the transport layer.
        """
        dead: List[WebSocket] = []
        for ws in list(self._connections.keys()):
            try:
                await ws.send_text(message)
                self._message_counts[ws] = self._message_counts.get(ws, 0) + 1
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def client_count(self) -> int:
        return len(self._connections)

    def get_stats(self) -> dict:
        now = time.time()
        return {
            "client_count": len(self._connections),
            "clients": [
                {
                    "connected_for_s": round(now - t, 1),
                    "messages_sent":   self._message_counts.get(ws, 0),
                }
                for ws, t in self._connect_times.items()
            ],
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

manager = ConnectionManager()


# ── WebSocket endpoint handler ────────────────────────────────────────────────

async def websocket_endpoint(ws: WebSocket) -> None:
    """
    FastAPI WebSocket endpoint handler.
    Wire this into api.py with @app.websocket("/ws").

    Flow:
      1. Accept connection + subscribe to bus
      2. Replay last 100 events so dashboard populates immediately
      3. Loop: wait for next event from bus queue → send to client
      4. On timeout (15s): send PING keepalive
      5. On disconnect: unsubscribe + remove from pool
    """
    q = await manager.connect(ws)

    # Replay history so dashboard is immediately populated
    await manager.send_history(ws, n=100)

    try:
        while True:
            try:
                event: Event = await asyncio.wait_for(q.get(), timeout=15.0)
                await ws.send_text(event.to_json())

            except asyncio.TimeoutError:
                # No events for 15s — send keepalive PING
                ping = Event(type=PING, payload={"ts": time.time()})
                try:
                    await ws.send_text(ping.to_json())
                except Exception:
                    break  # Client gone

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WS handler error: %s", exc)
    finally:
        manager.disconnect(ws)
