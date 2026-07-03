"""
VERISYNTH V-SOC — Event Schemas

Typed Pydantic models for every event payload.
These define the contract between the backend Event Bus
and the React frontend — if a field changes here, it
must change in the frontend TypeScript types too.

Every schema maps to one EventBus event type constant.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Base ───────────────────────────────────────────────────────────────────────

class BaseEvent(BaseModel):
    """Envelope wrapping every event sent over WebSocket."""
    type:      str
    payload:   Dict[str, Any]
    timestamp: float
    sim_step:  int   = 0
    sim_time:  float = 0.0

    class Config:
        extra = "allow"


# ── SIM_START ──────────────────────────────────────────────────────────────────

class SimStartPayload(BaseModel):
    name:                str
    seed:                int
    max_steps:           int
    fixed_delta_seconds: float
    town:                str
    weather:             str


# ── SIM_STOP ───────────────────────────────────────────────────────────────────

class SimStopPayload(BaseModel):
    total_steps:     int
    total_spawned:   int
    total_desyncs:   int
    peak_vehicles:   int
    wall_time_s:     float
    total_alerts:    int
    total_injected:  int


# ── VEHICLE_UPDATE ─────────────────────────────────────────────────────────────

class VehicleState(BaseModel):
    """Per-vehicle state snapshot — sent every detection cycle."""
    vehicle_id:       str
    x:                float
    y:                float
    speed:            float
    heading:          float
    trust_score:      float
    composite_score:  float
    verdict:          str           # NORMAL | WARN | ISOLATE | RESTORE
    is_attacked:      bool
    attack_type:      Optional[str] = None
    is_isolated:      bool
    ids_confidence:   float
    anomaly_score:    float


class VehicleUpdatePayload(BaseModel):
    vehicles:         List[VehicleState]
    active_count:     int
    isolated_count:   int
    warned_count:     int
    avg_trust:        float


# ── PACKET_STATS ───────────────────────────────────────────────────────────────

class PacketStatsPayload(BaseModel):
    total_delivered:  int
    attack_packets:   int
    normal_packets:   int
    packets_per_step: float
    by_attack_type:   Dict[str, int]


# ── ATTACK_START ───────────────────────────────────────────────────────────────

class AttackStartPayload(BaseModel):
    attack_type:      str
    target_vehicles:  List[str]
    start_step:       int
    end_step:         int
    triggered_by:     str           # "scheduled" | "dashboard"


# ── ATTACK_END ─────────────────────────────────────────────────────────────────

class AttackEndPayload(BaseModel):
    attack_type:      str
    total_injected:   int
    duration_steps:   int


# ── ATTACK_STATUS ──────────────────────────────────────────────────────────────

class AttackInfo(BaseModel):
    attack_type:      str
    enabled:          bool
    active:           bool
    start_step:       int
    end_step:         int
    total_injected:   int
    run_count:        int


class AttackStatusPayload(BaseModel):
    attacks:          List[AttackInfo]
    total_injected:   int
    any_active:       bool


# ── IDS_ALERT ──────────────────────────────────────────────────────────────────

class IDSAlertPayload(BaseModel):
    vehicle_id:       str
    alert_type:       str           # REPLAY | SPOOFING | DOS | SYBIL | GPS_SPOOFING | FORCEFUL | ZERO_DAY | CRITICAL_ZERO_DAY | UNKNOWN_ANOMALY
    severity:         str           # HIGH | MEDIUM | LOW | CRITICAL
    confidence:       float
    action:           str           # BLOCK | MONITOR | LOG
    source:           str           # RULE | ML | AUTOENCODER | FUSION
    rule_triggered:   Optional[str] = None
    anomaly_score:    float         = 0.0
    fused_score:      float         = 0.0
    n_detectors:      int           = 0
    corroborated:     bool          = False
    trust_at_alert:   float         = 0.0


# ── TRUST_CHANGE ───────────────────────────────────────────────────────────────

class TrustChangePayload(BaseModel):
    vehicle_id:       str
    verdict:          str           # ISOLATE | RESTORE
    action:           str           # ISOLATED | LIFTED_ISOLATION
    composite_score:  float
    ids_score:        float
    anomaly_score:    float
    history_score:    float


# ── TRUST_SNAPSHOT ─────────────────────────────────────────────────────────────

class VehicleTrustEntry(BaseModel):
    vehicle_id:       str
    trust_score:      float
    composite_score:  float
    verdict:          str
    isolated:         bool
    warned:           bool


class TrustSnapshotPayload(BaseModel):
    vehicles:         List[VehicleTrustEntry]
    avg_trust:        float
    min_trust:        float
    max_trust:        float
    isolated_count:   int
    warned_count:     int


# ── SCENE_CHANGE ───────────────────────────────────────────────────────────────

class SceneChangePayload(BaseModel):
    change_type:      str           # "town" | "weather" | "daytime"
    value:            Any
    success:          bool
    current_town:     str
    current_weather:  str
    sun_altitude:     float
    requested_by:     str


# ── MODEL_STATUS ───────────────────────────────────────────────────────────────

class ModelStatusPayload(BaseModel):
    # CNN-LSTM
    cnn_trained:          bool
    cnn_val_acc:          float
    cnn_rounds:           int
    # Autoencoder
    ae_trained:           bool
    ae_threshold:         float
    ae_ema_mean:          float
    ae_drift_count:       int
    ae_drift_retrains:    int
    ae_replay_buf_size:   int
    # Zero-day
    zero_day_alerts:      int
    critical_alerts:      int
    zero_day_vehicles:    List[str]
    # Federated Learning
    fl_round:             int
    fl_strategy:          str
    # General
    total_predictions:    int
    detection_rate:       float
    false_positive_rate:  float


# ── SYSTEM_HEALTH ──────────────────────────────────────────────────────────────

class SystemHealthPayload(BaseModel):
    cpu_percent:          float
    memory_percent:       float
    gpu_percent:          float
    disk_percent:         float
    ws_clients:           int
    event_bus_published:  int
    event_bus_dropped:    int
    sim_step:             int
    sim_fps:              float
    packet_throughput:    int


# ── REST API response models ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:           str
    service:          str
    version:          str
    sim_running:      bool
    ws_clients:       int
    event_bus:        Dict[str, Any]


class AttackControlRequest(BaseModel):
    attack_type:      str
    duration_steps:   Optional[int] = None


class SceneControlRequest(BaseModel):
    change_type:      str           # "town" | "weather" | "daytime"
    value:            str


class SimControlRequest(BaseModel):
    action:           str           # "start" | "stop" | "pause" | "resume"
