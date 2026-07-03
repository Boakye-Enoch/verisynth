"""
VERISYNTH V-SOC — Event Bus

Central in-process async event bus.

Design:
  - Simulation thread calls publish() from CosimSync._run_step()
  - FastAPI/WebSocket thread subscribes and receives events asynchronously
  - Thread-safe: threading.Lock protects shared state; asyncio boundary
    is crossed via loop.call_soon_threadsafe with a safe wrapper callback
  - History stored in collections.deque — O(1) append and eviction
  - Every event carries a unique event_id for deduplication and replay
  - QueueFull handled via wrapped callback — never raises in async loop
  - Never blocks the simulation loop under any circumstances

Event publication order per step (deterministic):
  1. VEHICLE_UPDATE    — vehicle telemetry + trust state
  2. ATTACK_STATUS     — active/inactive per attack type
  3. ATTACK_START/END  — transitions only (not every step)
  4. IDS_ALERT         — new alerts since last step
  5. TRUST_SNAPSHOT    — composite scores for all vehicles
  6. TRUST_CHANGE      — isolation/restore transitions
  7. MODEL_STATUS      — every 20 steps
  8. SYSTEM_HEALTH     — every 100 steps (from health monitor)
  9. SCENE_CHANGE      — only when a change was applied
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Event type constants ───────────────────────────────────────────────────────

SIM_START      = "SIM_START"
SIM_STOP       = "SIM_STOP"
VEHICLE_UPDATE = "VEHICLE_UPDATE"
PACKET_STATS   = "PACKET_STATS"
ATTACK_START   = "ATTACK_START"
ATTACK_END     = "ATTACK_END"
ATTACK_STATUS  = "ATTACK_STATUS"
IDS_ALERT      = "IDS_ALERT"
TRUST_CHANGE   = "TRUST_CHANGE"
TRUST_SNAPSHOT = "TRUST_SNAPSHOT"
SCENE_CHANGE   = "SCENE_CHANGE"
MODEL_STATUS   = "MODEL_STATUS"
SYSTEM_HEALTH  = "SYSTEM_HEALTH"
KEY_ROTATION   = "KEY_ROTATION"
PING           = "PING"
SECURITY_MODE  = "SECURITY_MODE"


# ── Core event dataclass ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Event:
    """
    A single event on the bus.

    event_id : globally unique identifier — used for deduplication
               on dashboard reconnect and replay buffer indexing
    type     : one of the constants above
    payload  : event-specific data dict — flat, JSON-serialisable
    timestamp: wall-clock seconds since epoch (not sim time)
    sim_step : simulation step when event was created
    sim_time : simulation time in seconds
    """
    type:      str
    payload:   Dict[str, Any] = field(default_factory=dict)
    timestamp: float          = field(default_factory=time.time)
    sim_step:  int            = 0
    sim_time:  float          = 0.0
    event_id:  str            = field(default_factory=lambda: str(uuid.uuid4()))
    seq:       int            = 0  # monotonic sequence, stamped by EventBus.publish()

    def to_json(self) -> str:
        return json.dumps({
            "event_id":  self.event_id,
            "seq":       self.seq,
            "type":      self.type,
            "payload":   self.payload,
            "timestamp": self.timestamp,
            "sim_step":  self.sim_step,
            "sim_time":  round(self.sim_time, 4),
        }, default=str)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":  self.event_id,
            "seq":       self.seq,
            "type":      self.type,
            "payload":   self.payload,
            "timestamp": self.timestamp,
            "sim_step":  self.sim_step,
            "sim_time":  round(self.sim_time, 4),
        }


# ── Event Bus ─────────────────────────────────────────────────────────────────

class EventBus:
    """
    In-process async event bus — thread-safe, non-blocking.

    Thread safety:
      _lock protects: _subscribers list, _history deque, _publish_counts,
      _total_published, _total_dropped. All mutations go through the lock.

      The asyncio boundary is crossed by scheduling a safe _enqueue()
      callback via call_soon_threadsafe — the callback itself does a
      non-blocking put_nowait inside the async thread, so QueueFull
      is caught there rather than propagating into the simulation thread.
    """

    def __init__(
        self,
        history_size:  int = 500,
        queue_maxsize: int = 512,
    ) -> None:
        self._history_size  = history_size
        self._queue_maxsize = queue_maxsize

        # Protected by _lock
        self._lock:        threading.Lock              = threading.Lock()
        self._subscribers: List[asyncio.Queue]         = []
        self._history:     Deque[Event]                = deque(maxlen=history_size)
        self._publish_counts: Dict[str, int]           = {}
        self._total_published: int                     = 0
        self._total_dropped:   int                     = 0
        self._seq_counter:     int                     = 0

        # Set once from async context — read from simulation thread (no lock
        # needed: written before simulation starts, read-only after that)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        logger.info(
            "EventBus created | history=%d queue_max=%d",
            history_size, queue_maxsize,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Register the running asyncio event loop.
        Called once from FastAPI startup — before simulation publishes.
        After this call, _loop is read-only from the simulation thread.
        """
        self._loop = loop
        logger.info("EventBus | asyncio loop registered")

    # ── Subscription ─────────────────────────────────────────────────────────

    def subscribe(self) -> asyncio.Queue:
        """
        Create and register a new subscriber queue.
        Must be called from the async thread (WebSocket handler).
        """
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_maxsize)
        with self._lock:
            self._subscribers.append(q)
        logger.debug(
            "EventBus | subscriber added | total=%d",
            len(self._subscribers),
        )
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        """Remove a subscriber queue. Called when WebSocket disconnects.
        Future: add health monitoring to auto-evict persistently-full queues.
        """
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s is not q]
        logger.debug(
            "EventBus | subscriber removed | total=%d",
            len(self._subscribers),
        )

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, event: Event) -> None:
        """
        Thread-safe publish from the simulation thread.

        1. Appends to history under lock (deque evicts oldest automatically)
        2. Updates counters under lock
        3. Schedules _enqueue(event, q) on the asyncio loop for each subscriber
           — call_soon_threadsafe is the safe crossing point; the actual
           put_nowait happens on the async thread, so QueueFull is caught
           there and never surfaces into the simulation loop
        """
        with self._lock:
            self._seq_counter += 1
            # Stamp monotonic sequence number onto frozen event.
            # object.__setattr__ is the standard pattern for trusted
            # internal mutation of frozen dataclasses — only the bus
            # ever does this, immediately after creation.
            object.__setattr__(event, "seq", self._seq_counter)
            self._history.append(event)
            self._total_published += 1
            self._publish_counts[event.type] = (
                self._publish_counts.get(event.type, 0) + 1
            )
            subscribers_snapshot = list(self._subscribers)

        if self._loop is None or not self._loop.is_running():
            return  # Server not yet up — history-only, no subscribers yet

        for q in subscribers_snapshot:
            # Schedule a safe enqueue callback on the async thread
            # If the loop is shutting down, schedule_callback raises — catch it
            try:
                self._loop.call_soon_threadsafe(self._enqueue, event, q)
            except RuntimeError:
                pass  # Loop closed — simulation is shutting down

    def _enqueue(self, event: Event, q: asyncio.Queue) -> None:
        """
        Called on the asyncio thread via call_soon_threadsafe.
        Does a non-blocking put — if the queue is full, drops and counts.
        This is the safe side of the thread boundary; exceptions here
        are isolated to the async thread and never affect the simulation.
        """
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            with self._lock:
                self._total_dropped += 1
            logger.debug("EventBus | queue full — event dropped | type=%s", event.type)
        except Exception as exc:
            logger.warning("EventBus | enqueue error: %s", exc)

    def publish_dict(
        self,
        event_type: str,
        payload:    Dict[str, Any],
        sim_step:   int   = 0,
        sim_time:   float = 0.0,
    ) -> None:
        """
        Convenience wrapper — avoids importing Event dataclass in adapters.
        event_id is auto-generated by Event.__init__.
        """
        self.publish(Event(
            type     = event_type,
            payload  = payload,
            sim_step = sim_step,
            sim_time = sim_time,
        ))

    # ── History ───────────────────────────────────────────────────────────────

    @property
    def history(self) -> List[Event]:
        """Snapshot of current history. Thread-safe."""
        with self._lock:
            return list(self._history)

    def get_history(
        self,
        n:          Optional[int] = None,
        event_type: Optional[str] = None,
    ) -> List[Event]:
        """
        Filtered history snapshot.
        Used by /events/history REST endpoint and WebSocket reconnect replay.
        """
        with self._lock:
            events = list(self._history)

        if event_type:
            events = [e for e in events if e.type == event_type]
        if n:
            events = events[-n:]
        return events

    def clear_history(self) -> None:
        """Clear history between simulation runs."""
        with self._lock:
            self._history.clear()
            self._publish_counts.clear()
            self._total_published = 0
            self._total_dropped   = 0

    # ── Status ────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Stats for /health endpoint and SYSTEM_HEALTH event payload."""
        with self._lock:
            return {
                "total_published":  self._total_published,
                "total_dropped":    self._total_dropped,
                "drop_rate":        round(
                    self._total_dropped / max(self._total_published, 1), 4
                ),
                "history_size":     len(self._history),
                "history_capacity": self._history_size,
                "subscriber_count": len(self._subscribers),
                "loop_running":     (
                    self._loop is not None and self._loop.is_running()
                ),
                "seq_counter":      self._seq_counter,
                "by_type":          dict(self._publish_counts),
            }

    def summary(self) -> str:
        stats = self.get_stats()
        return (
            f"EventBus | "
            f"published={stats['total_published']} "
            f"dropped={stats['total_dropped']} "
            f"drop_rate={stats['drop_rate']:.2%} "
            f"subscribers={stats['subscriber_count']} "
            f"history={stats['history_size']}"
        )


# ── Singleton ─────────────────────────────────────────────────────────────────

bus = EventBus()
