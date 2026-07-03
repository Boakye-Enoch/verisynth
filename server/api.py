"""
VERISYNTH V-SOC — FastAPI Application

Exposes:
  WS   /ws                    — real-time event stream
  GET  /health                — server + simulation health
  GET  /events/history        — last N events (for page refresh)
  GET  /events/history/{type} — filtered by event type
  GET  /sim/status            — current simulation state snapshot
  GET  /attacks/status        — current attack states
  POST /attacks/activate      — start an attack from dashboard
  POST /attacks/deactivate    — stop an attack from dashboard
  POST /attacks/deactivate_all— emergency stop all attacks
  GET  /scene/status          — current town/weather
  POST /scene/change          — switch town / weather / daytime
  GET  /trust/snapshot        — current trust scores for all vehicles
  GET  /ids/alerts            — recent IDS alerts
  GET  /metrics               — system metrics (CPU/mem/etc)

Design:
  - All simulation control endpoints are thread-safe:
    they call methods on objects that are already thread-safe
    (AttackScheduler.activate_attack, SceneController.request_*)
  - Simulation state is read-only from the API thread
  - sim_step is carried in a shared SimState object updated each step
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import psutil
from fastapi import FastAPI, WebSocket, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.event_bus import bus, SYSTEM_HEALTH
from server.ws_manager import manager, websocket_endpoint
from server.schemas import (
    HealthResponse,
    AttackControlRequest,
    SceneControlRequest,
    SimControlRequest,
)

logger = logging.getLogger(__name__)


# ── Shared simulation state (written by simulation thread, read by API) ────────

class SimState:
    """
    Lightweight shared state container.
    Written by the simulation thread each step via update().
    Read by API endpoints (no lock needed — reads are atomic for small values).

    Consistency model:
      - Only lightweight scalar values (int, float, str, bool) are stored here.
      - Slight timing inconsistencies between fields are acceptable and expected
        (e.g. sim_step and total_alerts may differ by one detection cycle).
      - Object references (attack_scheduler, scene_controller, etc.) are set
        once before the simulation starts and never replaced — safe to read
        from any thread without locking.
      - If complex mutable objects are added later, introduce a threading.Lock
        or replace mutable fields with immutable snapshots.

    Future: as the system grows, introduce a SimulationController service
    that owns all subsystem references and exposes a clean public API,
    keeping api.py independent of internal subsystem implementations.
    """
    def __init__(self):
        self.running:         bool  = False
        self.sim_step:        int   = 0
        self.sim_time:        float = 0.0
        self.current_town:    str   = "Town04"
        self.current_weather: str   = "ClearNoon"
        self.peak_vehicles:   int   = 0
        self.total_alerts:    int   = 0
        self.total_injected:  int   = 0
        self.start_wall_time: float = 0.0

        # References to live subsystems (set by main.py before sim starts)
        self.attack_scheduler   = None
        self.scene_controller   = None
        self.ids_manager        = None
        self.trust_orchestrator = None

    def update(self, sim_step: int, sim_time: float) -> None:
        self.sim_step = sim_step
        self.sim_time = sim_time

    def mark_running(self) -> None:
        self.running = True
        self.start_wall_time = time.time()

    def mark_stopped(self) -> None:
        self.running = False


# Singleton — imported by main.py to wire subsystems
sim_state = SimState()


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "VERISYNTH V-SOC API",
    description = "Real-time V2X Security Operations Center — API on port 8001",
    version     = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # tighten to dashboard origin in deployment
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ── Startup ────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """Register the asyncio loop with the event bus so publish() works."""
    bus.set_loop(asyncio.get_event_loop())
    asyncio.create_task(_health_heartbeat())
    logger.info("VERISYNTH V-SOC API started | bus loop registered")


async def _health_heartbeat() -> None:
    """Emit SYSTEM_HEALTH event every 5 seconds."""
    while True:
        await asyncio.sleep(5)
        try:
            bus.publish_dict(SYSTEM_HEALTH, {
                "cpu_percent":         psutil.cpu_percent(interval=0.1),
                "memory_percent":      psutil.virtual_memory().percent,
                "gpu_percent":         0.0,  # extend with GPUtil if available
                "disk_percent":        psutil.disk_usage("/").percent,
                "ws_clients":          manager.client_count,
                "event_bus_published": bus.get_stats()["total_published"],
                "event_bus_dropped":   bus.get_stats()["total_dropped"],
                "sim_step":            sim_state.sim_step,
                "sim_fps":             round(
                    sim_state.sim_step / max(
                        time.time() - sim_state.start_wall_time, 1.0
                    ), 2
                ) if sim_state.running else 0.0,
                "packet_throughput":   0,
            })
        except Exception as exc:
            logger.warning("Health heartbeat error: %s", exc)


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_route(ws: WebSocket) -> None:
    await websocket_endpoint(ws)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status      = "ok",
        service     = "VERISYNTH V-SOC",
        version     = "2.0.0",
        sim_running = sim_state.running,
        ws_clients  = manager.client_count,
        event_bus   = bus.get_stats(),
    )


# ── Event history ──────────────────────────────────────────────────────────────

@app.get("/events/history")
async def event_history(limit: int = 100) -> JSONResponse:
    """Last N events — used when dashboard (re)loads to populate panels."""
    events = bus.get_history(n=limit)
    return JSONResponse([e.to_dict() for e in events])


@app.get("/events/history/{event_type}")
async def event_history_by_type(event_type: str, limit: int = 50) -> JSONResponse:
    """Last N events of a specific type."""
    events = bus.get_history(n=limit, event_type=event_type.upper())
    return JSONResponse([e.to_dict() for e in events])


# ── Simulation status ──────────────────────────────────────────────────────────

@app.get("/sim/status")
async def sim_status() -> JSONResponse:
    sc = sim_state.scene_controller
    return JSONResponse({
        "running":         sim_state.running,
        "sim_step":        sim_state.sim_step,
        "sim_time":        round(sim_state.sim_time, 2),
        "current_town":    sc.current_town    if sc else sim_state.current_town,
        "current_weather": sc.current_weather if sc else sim_state.current_weather,
        "peak_vehicles":   sim_state.peak_vehicles,
        "total_alerts":    sim_state.total_alerts,
        "total_injected":  sim_state.total_injected,
        "wall_time_s":     round(
            time.time() - sim_state.start_wall_time, 1
        ) if sim_state.running else 0.0,
    })


# ── Attack control ─────────────────────────────────────────────────────────────

@app.get("/attacks/status")
async def attacks_status() -> JSONResponse:
    if not sim_state.attack_scheduler:
        return JSONResponse({"error": "Simulation not running"}, status_code=503)
    return JSONResponse(sim_state.attack_scheduler.get_status())


@app.post("/attacks/activate")
async def activate_attack(req: AttackControlRequest) -> JSONResponse:
    if not sim_state.attack_scheduler:
        raise HTTPException(503, "Simulation not running")

    # Get current vehicle list from trust manager (approximate live state)
    sumo_states = _get_fake_sumo_states()
    result = sim_state.attack_scheduler.activate_attack(
        attack_type    = req.attack_type.upper(),
        sim_step       = sim_state.sim_step,
        sumo_states    = sumo_states,
        duration_steps = req.duration_steps,
    )
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Activation failed"))
    return JSONResponse(result)


@app.post("/attacks/deactivate")
async def deactivate_attack(req: AttackControlRequest) -> JSONResponse:
    if not sim_state.attack_scheduler:
        raise HTTPException(503, "Simulation not running")
    result = sim_state.attack_scheduler.deactivate_attack(
        attack_type = req.attack_type.upper(),
        sim_step    = sim_state.sim_step,
    )
    if not result["success"]:
        raise HTTPException(400, result.get("error", "Deactivation failed"))
    return JSONResponse(result)


@app.post("/attacks/deactivate_all")
async def deactivate_all_attacks() -> JSONResponse:
    if not sim_state.attack_scheduler:
        raise HTTPException(503, "Simulation not running")
    result = sim_state.attack_scheduler.deactivate_all(sim_state.sim_step)
    return JSONResponse(result)


# ── Scene control ──────────────────────────────────────────────────────────────

@app.get("/scene/status")
async def scene_status() -> JSONResponse:
    if not sim_state.scene_controller:
        return JSONResponse({"error": "Simulation not running"}, status_code=503)
    return JSONResponse(sim_state.scene_controller.get_status())


@app.post("/scene/change")
async def scene_change(req: SceneControlRequest) -> JSONResponse:
    if not sim_state.scene_controller:
        raise HTTPException(503, "Simulation not running")

    sc = sim_state.scene_controller
    if req.change_type == "town":
        result = sc.request_town_change(req.value, requested_by="dashboard")
    elif req.change_type == "weather":
        result = sc.request_weather_change(req.value, requested_by="dashboard")
    elif req.change_type == "daytime":
        result = sc.request_daytime(req.value, requested_by="dashboard")
    else:
        raise HTTPException(400, f"Unknown change_type: {req.change_type}")

    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Scene change failed"))
    return JSONResponse(result)


# ── Trust ──────────────────────────────────────────────────────────────────────

@app.get("/trust/snapshot")
async def trust_snapshot() -> JSONResponse:
    """Current trust scores for all vehicles."""
    orch = sim_state.trust_orchestrator
    ids  = sim_state.ids_manager
    if not ids:
        return JSONResponse({"error": "Simulation not running"}, status_code=503)

    # TrustManager is accessed via IDSManager._trust — a future refactor
    # should expose get_all_trust_scores() as a public IDSManager method.
    trust_scores     = ids._trust.get_all_scores()
    composite_scores = orch.get_all_scores() if orch else {}
    isolated         = orch.isolated_vehicles if orch else set()
    warned           = orch.warned_vehicles   if orch else set()

    vehicles = [
        {
            "vehicle_id":      str(vid),
            "trust_score":     round(trust, 4),
            "composite_score": round(composite_scores.get(vid, 0.0), 4),
            "isolated":        vid in isolated,
            "warned":          vid in warned,
        }
        for vid, trust in trust_scores.items()
    ]
    scores = [v["trust_score"] for v in vehicles]
    return JSONResponse({
        "vehicles":       vehicles,
        "avg_trust":      round(sum(scores)/len(scores), 4) if scores else 0.0,
        "isolated_count": len(isolated),
        "warned_count":   len(warned),
    })


# ── IDS alerts ─────────────────────────────────────────────────────────────────

@app.get("/ids/alerts")
async def ids_alerts(limit: int = 50) -> JSONResponse:
    """Recent IDS alert records."""
    if not sim_state.ids_manager:
        return JSONResponse({"error": "Simulation not running"}, status_code=503)

    # Access via public alert_manager property (not internal _history directly)
    am      = sim_state.ids_manager.alert_manager
    # AlertManager exposes _history — add a public accessor in a future
    # refactor. For now we document the dependency explicitly.
    records = list(am._history[-limit:])
    return JSONResponse([
        {
            "vehicle_id":  r.alert.vehicle_id,
            "alert_type":  r.alert.alert_type,
            "severity":    r.alert.severity,
            "confidence":  round(r.alert.confidence, 4),
            "action":      r.action,
            "source":      r.alert.source,
            "sim_step":    r.alert.sim_step,
            "sim_time":    round(r.alert.sim_time, 4),
        }
        for r in records
    ])


# ── Security Mode Control ─────────────────────────────────────────────────────────

class SecurityModeRequest(BaseModel):
    enabled: bool

@app.get("/security/status")
async def security_status() -> JSONResponse:
    """Current state of all security mechanisms."""
    ids  = sim_state.ids_manager
    can  = sim_state.__dict__.get('can_bus')
    km   = sim_state.__dict__.get('key_manager')
    orch = sim_state.trust_orchestrator

    return JSONResponse({
        "ids_enabled":          ids._enabled if ids else False,
        "trust_orch_enabled":   sim_state.__dict__.get('trust_orch_enabled', True),
        "can_auth_enabled":     getattr(getattr(can, '_auth', None), '_enabled', True) if can else True,
        "key_mgmt_enabled":     getattr(km, '_enabled', True) if km else True,
        "overall_protected":    sim_state.__dict__.get('security_mode', True),
    })

@app.post("/security/mode")
async def set_security_mode(req: SecurityModeRequest) -> JSONResponse:
    """
    Enable or disable ALL security mechanisms simultaneously.
    OFF = attacker mode: attacks run, nothing detects or mitigates them.
    ON  = protected mode: IDS, Trust, CAN auth, key management all active.
    """
    enabled = req.enabled
    sim_state.__dict__['security_mode'] = enabled
    sim_state.__dict__['trust_orch_enabled'] = enabled

    ids = sim_state.ids_manager
    if ids:
        ids._enabled = enabled
        # Also toggle trust manager penalties
        if not enabled:
            # When security is OFF, reset all trust scores to neutral
            # so vehicles appear unprotected (not isolated)
            for vid in list(ids._trust._trust.keys()):
                ids._trust._trust[vid] = 0.70

    # Toggle Trust Orchestrator
    orch = sim_state.trust_orchestrator
    if orch:
        if not enabled:
            # Clear all isolations so dashboard shows unprotected state
            for vid in list(orch._state.keys()):
                orch._state[vid].isolated    = False
                orch._state[vid].warn_active  = False
                orch._state[vid].last_verdict = "NORMAL"

    # Toggle CAN authentication
    can_bus = sim_state.__dict__.get('can_bus_ref')
    if can_bus and hasattr(can_bus, '_auth') and can_bus._auth:
        can_bus._auth._enabled = enabled

    # Toggle key manager
    km = sim_state.__dict__.get('key_manager_ref')
    if km:
        km._enabled = enabled

    from server.event_bus import bus
    bus.publish_dict("SECURITY_MODE", {
        "enabled":   enabled,
        "message":   "VERISYNTH protection ACTIVE" if enabled else "⚠ SECURITY DISABLED — attacks undetected",
    })

    logger.warning(
        "Security mode changed | enabled=%s by API request", enabled
    )
    return JSONResponse({
        "success": True,
        "enabled": enabled,
        "message": "Security ON — all mechanisms active" if enabled
                   else "Security OFF — system unprotected",
    })

# ── Metrics ────────────────────────────────────────────────────────────────────

@app.get("/metrics")
async def metrics() -> JSONResponse:
    return JSONResponse({
        "cpu_percent":    psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent":   psutil.disk_usage("/").percent,
        "ws_clients":     manager.client_count,
        "event_bus":      bus.get_stats(),
        "sim_step":       sim_state.sim_step,
        "sim_running":    sim_state.running,
    })


# ── Helper ─────────────────────────────────────────────────────────────────────

def _get_fake_sumo_states() -> List[Any]:
    """
    Return minimal vehicle state objects for attack activation.
    Attack scheduler only needs sumo_id from these for target selection.
    We build them from the trust manager's known vehicle set.
    """
    from dataclasses import dataclass

    @dataclass
    class MinimalState:
        sumo_id:  str
        x:        float = 0.0
        y:        float = 0.0
        angle:    float = 0.0
        speed:    float = 10.0
        type_id:  str   = "car"

    ids = sim_state.ids_manager
    if not ids:
        return []
    return [MinimalState(sumo_id=vid) for vid in ids._trust.get_all_scores()]
