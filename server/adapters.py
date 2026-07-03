"""
VERISYNTH V-SOC — Simulation Adapters

Translates live simulation state into typed Event Bus events.

Called once per simulation step from CosimSync._run_step()
via adapter.publish_step().

Publication order (deterministic, enforced by publish_step):
  1. VEHICLE_UPDATE
  2. ATTACK_STATUS + ATTACK_START/END transitions
  3. IDS_ALERT (new alerts only)
  4. TRUST_SNAPSHOT
  5. MODEL_STATUS (every 20 steps)
  6. SCENE_CHANGE (only when a change was applied)

Design rules:
  - Never mutates simulation state
  - Never raises — all errors logged and swallowed
  - Batches into single events per step (not one event per vehicle)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from server.event_bus import (
    bus,
    VEHICLE_UPDATE, ATTACK_STATUS, ATTACK_START, ATTACK_END,
    IDS_ALERT, TRUST_SNAPSHOT, MODEL_STATUS,
    SCENE_CHANGE, SIM_START, SIM_STOP,
)

logger = logging.getLogger(__name__)


class VERISYNTHAdapter:

    def __init__(self) -> None:
        self._ids_manager:        Optional[Any] = None
        self._trust_orchestrator: Optional[Any] = None
        self._attack_scheduler:   Optional[Any] = None
        self._scene_controller:   Optional[Any] = None

        self._prev_active_attacks: set = set()
        self._last_alert_ids:      set = set()
        self._step_count:          int = 0

        logger.info("VERISYNTHAdapter created")

    # ── Registration ──────────────────────────────────────────────────────────

    def register_ids_manager(self, ids_manager) -> None:
        self._ids_manager = ids_manager

    def register_trust_orchestrator(self, orchestrator) -> None:
        self._trust_orchestrator = orchestrator

    def register_attack_scheduler(self, scheduler) -> None:
        self._attack_scheduler = scheduler

    def register_scene_controller(self, scene_controller) -> None:
        self._scene_controller = scene_controller

    # ── Main step hook ────────────────────────────────────────────────────────

    def publish_step(
        self,
        sumo_states: List[Any],
        sim_step:    int,
        sim_time:    float,
        scene_change: Optional[Dict] = None,
    ) -> None:
        """
        Called once per step from CosimSync._run_step().
        Publication order is fixed — do not reorder calls.
        """
        self._step_count += 1

        # 1. Vehicle telemetry
        try:
            self._publish_vehicle_update(sumo_states, sim_step, sim_time)
        except Exception as exc:
            logger.warning("Adapter VEHICLE_UPDATE error: %s", exc)

        # 2. Attack status + transitions
        try:
            self._publish_attack_events(sim_step, sim_time)
        except Exception as exc:
            logger.warning("Adapter ATTACK_STATUS error: %s", exc)

        # 3. IDS alerts (new since last step)
        try:
            self._publish_ids_alerts(sim_step, sim_time)
        except Exception as exc:
            logger.warning("Adapter IDS_ALERT error: %s", exc)

        # 4. Trust snapshot
        try:
            self._publish_trust_snapshot(sim_step, sim_time)
        except Exception as exc:
            logger.warning("Adapter TRUST_SNAPSHOT error: %s", exc)

        # 5. Model status (every 20 steps)
        if self._step_count % 20 == 0:
            try:
                self._publish_model_status(sim_step, sim_time)
            except Exception as exc:
                logger.warning("Adapter MODEL_STATUS error: %s", exc)

        # 6. Scene change (only when one occurred this step)
        if scene_change and scene_change.get("success"):
            try:
                self._publish_scene_change(scene_change, sim_step, sim_time)
            except Exception as exc:
                logger.warning("Adapter SCENE_CHANGE error: %s", exc)

    # ── Vehicle update ────────────────────────────────────────────────────────

    def _publish_vehicle_update(self, sumo_states, sim_step, sim_time):
        if not sumo_states:
            return

        attacked_vehicles: Dict[str, str] = {}
        if self._attack_scheduler:
            for attack in self._attack_scheduler._attacks:
                if attack.is_active:
                    targets = (
                        getattr(attack, '_target_vehicles', []) or
                        getattr(attack, '_attackers', [])
                    )
                    for vid in targets:
                        attacked_vehicles[str(vid)] = attack.attack_type

        ids_scores: Dict[str, float] = {}
        anomaly_scores: Dict[str, float] = {}
        trust_scores: Dict[str, float] = {}
        if self._ids_manager:
            ids_scores, anomaly_scores = self._ids_manager.get_latest_scores()
            trust_scores = self._ids_manager._trust.get_all_scores()

        isolated_vids: set = set()
        warned_vids:   set = set()
        composite_scores: Dict[str, float] = {}
        if self._trust_orchestrator:
            isolated_vids    = self._trust_orchestrator.isolated_vehicles
            warned_vids      = self._trust_orchestrator.warned_vehicles
            composite_scores = self._trust_orchestrator.get_all_scores()

        vehicles = []
        trust_sum = 0.0

        for state in sumo_states:
            vid   = str(state.sumo_id)
            trust = trust_scores.get(vid, 0.70)
            comp  = composite_scores.get(vid, 0.0)
            trust_sum += trust

            verdict = "NORMAL"
            if self._trust_orchestrator:
                verdict = self._trust_orchestrator.get_verdict(vid)

            vehicles.append({
                "vehicle_id":      vid,
                "x":               round(state.x, 2),
                "y":               round(state.y, 2),
                "speed":           round(state.speed, 2),
                "heading":         round(state.angle, 2),
                "trust_score":     round(trust, 4),
                "composite_score": round(comp, 4),
                "verdict":         verdict,
                "is_attacked":     vid in attacked_vehicles,
                "attack_type":     attacked_vehicles.get(vid),
                "is_isolated":     vid in isolated_vids,
                "ids_confidence":  round(ids_scores.get(vid, 0.0), 4),
                "anomaly_score":   round(anomaly_scores.get(vid, 0.0), 4),
            })

        n = len(sumo_states)
        avg_trust = round(trust_sum / n, 4) if n > 0 else 0.0

        bus.publish_dict(VEHICLE_UPDATE, {
            "vehicles":       vehicles,
            "active_count":   n,
            "isolated_count": len(isolated_vids),
            "warned_count":   len(warned_vids),
            "avg_trust":      avg_trust,
        }, sim_step=sim_step, sim_time=sim_time)

    # ── Attack events ─────────────────────────────────────────────────────────

    def _publish_attack_events(self, sim_step, sim_time):
        if not self._attack_scheduler:
            return

        status = self._attack_scheduler.get_status()
        currently_active = {
            a["attack_type"] for a in status["attacks"] if a["active"]
        }

        # ATTACK_START transitions
        for atype in currently_active - self._prev_active_attacks:
            attack  = self._attack_scheduler._find_attack(atype)
            targets = list(
                getattr(attack, '_target_vehicles', []) or
                getattr(attack, '_attackers', [])
            )
            bus.publish_dict(ATTACK_START, {
                "attack_type":     atype,
                "target_vehicles": [str(v) for v in targets],
                "start_step":      attack.start_step,
                "end_step":        attack.end_step,
                "triggered_by":    "dashboard" if attack.run_count > 1 else "scheduled",
            }, sim_step=sim_step, sim_time=sim_time)

        # ATTACK_END transitions
        for atype in self._prev_active_attacks - currently_active:
            attack = self._attack_scheduler._find_attack(atype)
            if attack:
                bus.publish_dict(ATTACK_END, {
                    "attack_type":    atype,
                    "total_injected": attack.stats.total_injected,
                    "duration_steps": sim_step - attack.start_step,
                }, sim_step=sim_step, sim_time=sim_time)

        self._prev_active_attacks = currently_active

        # Full ATTACK_STATUS snapshot every step
        attacks_list = []
        for a in status["attacks"]:
            obj = self._attack_scheduler._find_attack(a["attack_type"])
            attacks_list.append({
                **a,
                "run_count": getattr(obj, 'run_count', 0),
            })

        bus.publish_dict(ATTACK_STATUS, {
            "attacks":        attacks_list,
            "total_injected": status["total_injected"],
            "any_active":     len(currently_active) > 0,
        }, sim_step=sim_step, sim_time=sim_time)

    # ── IDS alerts ────────────────────────────────────────────────────────────

    def _publish_ids_alerts(self, sim_step, sim_time):
        if not self._ids_manager:
            return

        am = self._ids_manager.alert_manager
        if not am._history:
            return

        new_alerts = [r for r in am._history if id(r) not in self._last_alert_ids]

        for record in new_alerts:
            self._last_alert_ids.add(id(record))
            a        = record.alert
            evidence = a.evidence or {}

            bus.publish_dict(IDS_ALERT, {
                "vehicle_id":     a.vehicle_id,
                "alert_type":     a.alert_type,
                "severity":       a.severity,
                "confidence":     round(a.confidence, 4),
                "action":         record.action,
                "source":         a.source,
                "rule_triggered": a.rule_triggered,
                "anomaly_score":  round(a.anomaly_score, 4),
                "fused_score":    round(evidence.get("fused_score", 0.0), 4),
                "n_detectors":    evidence.get("n_detectors", 0),
                "corroborated":   evidence.get("corroborated", False),
                "trust_at_alert": round(evidence.get("trust", 0.0), 4),
            }, sim_step=a.sim_step, sim_time=a.sim_time)

        if len(self._last_alert_ids) > 10000:
            self._last_alert_ids = set(list(self._last_alert_ids)[-5000:])

    # ── Trust snapshot ────────────────────────────────────────────────────────

    def _publish_trust_snapshot(self, sim_step, sim_time):
        if not self._ids_manager or not self._trust_orchestrator:
            return

        trust_scores     = self._ids_manager._trust.get_all_scores()
        composite_scores = self._trust_orchestrator.get_all_scores()
        isolated_vids    = self._trust_orchestrator.isolated_vehicles
        warned_vids      = self._trust_orchestrator.warned_vehicles

        if not trust_scores:
            return

        vehicles = []
        for vid, trust in trust_scores.items():
            vehicles.append({
                "vehicle_id":      str(vid),
                "trust_score":     round(trust, 4),
                "composite_score": round(composite_scores.get(vid, 0.0), 4),
                "verdict":         self._trust_orchestrator.get_verdict(vid),
                "isolated":        vid in isolated_vids,
                "warned":          vid in warned_vids,
            })

        scores = [v["trust_score"] for v in vehicles]
        bus.publish_dict(TRUST_SNAPSHOT, {
            "vehicles":       vehicles,
            "avg_trust":      round(sum(scores) / len(scores), 4),
            "min_trust":      round(min(scores), 4),
            "max_trust":      round(max(scores), 4),
            "isolated_count": len(isolated_vids),
            "warned_count":   len(warned_vids),
        }, sim_step=sim_step, sim_time=sim_time)

    # ── Model status ──────────────────────────────────────────────────────────

    def _publish_model_status(self, sim_step, sim_time):
        if not self._ids_manager:
            return

        ids = self._ids_manager
        ae  = ids._anomaly_detector
        ml  = ids._ml_detector
        tr  = ids._trainer
        am  = ids.alert_manager

        ae_status = {}
        if hasattr(ae, "get_adaptive_status"):
            ae_status = ae.get_adaptive_status()

        total_rx       = max(am._total_rx, 1)
        detection_rate = round(am._total_emit / total_rx, 4)

        bus.publish_dict(MODEL_STATUS, {
            "cnn_trained":        ml.is_trained,
            "cnn_val_acc":        round(getattr(tr, '_last_val_acc', 0.0), 4),
            "cnn_rounds":         getattr(tr, '_round_count', 0),
            "ae_trained":         ae.is_trained,
            "ae_threshold":       round(ae.threshold if ae.threshold < 1e9 else 0.0, 6),
            "ae_ema_mean":        round(ae_status.get("ema_mean", 0.0), 6),
            "ae_drift_count":     ae_status.get("drift_count", 0),
            "ae_drift_retrains":  ae_status.get("drift_retrains", 0),
            "ae_replay_buf_size": ae_status.get("replay_buffer_size", 0),
            "zero_day_alerts":    ae_status.get("zero_day_alerts", 0),
            "critical_alerts":    ae_status.get("critical_alerts", 0),
            "zero_day_vehicles":  ae_status.get("zero_day_vehicles", []),
            "fl_round":           getattr(tr, '_round_count', 0),
            "fl_strategy":        "TrimmedMean",
            "total_predictions":  ids._total_alerts,
            "detection_rate":     detection_rate,
            "false_positive_rate": 0.0,
        }, sim_step=sim_step, sim_time=sim_time)

    # ── Scene change ──────────────────────────────────────────────────────────

    def _publish_scene_change(self, change, sim_step, sim_time):
        sc = self._scene_controller
        bus.publish_dict(SCENE_CHANGE, {
            "change_type":     change.get("change_type"),
            "value":           change.get("value"),
            "success":         True,
            "current_town":    sc.current_town    if sc else "",
            "current_weather": sc.current_weather if sc else "",
            "sun_altitude":    sc._sun_altitude   if sc else 60.0,
            "requested_by":    change.get("requested_by", "system"),
        }, sim_step=sim_step, sim_time=sim_time)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def publish_sim_start(self, sim_cfg: dict, town: str, weather: str) -> None:
        bus.publish_dict(SIM_START, {
            "name":                sim_cfg.get("name", "verisynth"),
            "seed":                sim_cfg.get("seed", 42),
            "max_steps":           sim_cfg.get("max_steps", 6000),
            "fixed_delta_seconds": sim_cfg.get("fixed_delta_seconds", 0.05),
            "town":                town,
            "weather":             weather,
        })

    def publish_sim_stop(self, stats, total_alerts: int, total_injected: int) -> None:
        bus.publish_dict(SIM_STOP, {
            "total_steps":    getattr(stats, "total_steps", 0),
            "total_spawned":  getattr(stats, "total_spawned", 0),
            "total_desyncs":  getattr(stats, "total_desyncs", 0),
            "peak_vehicles":  getattr(stats, "peak_vehicles", 0),
            "total_alerts":   total_alerts,
            "total_injected": total_injected,
        })


# ── Singleton ─────────────────────────────────────────────────────────────────

adapter = VERISYNTHAdapter()
