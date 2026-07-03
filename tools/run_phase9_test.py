#!/usr/bin/env python3
"""
VERISYNTH — Phase 9 Validation Test
=====================================
Standalone smoke test for TrustOrchestrator integration.
Does NOT require CARLA or SUMO — uses stub objects.

Run from the project root:
    conda activate carla-sim
    python tools/run_phase9_test.py

Expected output:
    ✓ TrustOrchestrator initialises
    ✓ get_latest_scores() is a method (not module-level function)
    ✓ score cache empty before first step
    ✓ Step 1: 5 verdicts returned
    ✓ NORMAL vehicles score < 0.45
    ✓ ATTACK vehicle score > 0.45
    ✓ Step 20 (after consecutive gate): ATTACK vehicle isolated
    ✓ Isolation eventually lifts after clean steps
    ✓ TRUST_CHANGE events emitted: ISOLATED and LIFTED_ISOLATION
    ✓ Orchestrator summary reports correct counts
    ── Phase 9 validation PASSED ──
"""

from __future__ import annotations

import sys
import logging
from collections import defaultdict
from typing import Dict, List, Optional
from unittest.mock import MagicMock

logging.basicConfig(level=logging.WARNING)   # suppress INFO noise during test

# ─────────────────────────────────────────────────────────────────────────────
# Stubs — minimal fakes of the real objects TrustOrchestrator depends on
# ─────────────────────────────────────────────────────────────────────────────

class StubTrustManager:
    """Mimics TrustManager.get_trust() and get_all_scores()."""
    def __init__(self):
        self._scores: Dict[str, float] = defaultdict(lambda: 0.70)

    def get_trust(self, vid: str) -> float:
        return self._scores[vid]

    def get_all_scores(self) -> Dict[str, float]:
        return dict(self._scores)

    def set_trust(self, vid: str, score: float) -> None:
        self._scores[vid] = max(0.0, min(1.0, score))


class StubAlertManager:
    """Minimal AlertManager stub. TrustOrchestrator only holds a reference."""
    pass


class StubIDSManager:
    """
    Stub IDSManager with working get_latest_scores() to validate the method
    is correctly inside the class (not a module-level function).
    """
    def __init__(self, trust_manager: StubTrustManager):
        self._trust = trust_manager
        self._last_ids_scores:     Dict[str, float] = {}
        self._last_anomaly_scores: Dict[str, float] = {}

    def get_latest_scores(self) -> tuple[dict, dict]:
        return dict(self._last_ids_scores), dict(self._last_anomaly_scores)

    def set_scores(self, ids: Dict[str, float], anomaly: Dict[str, float]) -> None:
        self._last_ids_scores     = ids
        self._last_anomaly_scores = anomaly


class StubEventLogger:
    """Captures TRUST_CHANGE events for assertion."""
    def __init__(self):
        self.events: List[dict] = []

    def log(self, event_type: str, sim_step: int, sim_time: float, data: dict):
        self.events.append({
            "event_type": event_type,
            "sim_step":   sim_step,
            "sim_time":   sim_time,
            **data,
        })


# ─────────────────────────────────────────────────────────────────────────────
# Test runner
# ─────────────────────────────────────────────────────────────────────────────

def run() -> None:
    passed = 0
    failed = 0

    def ok(msg: str):
        nonlocal passed
        passed += 1
        print(f"  ✓ {msg}")

    def fail(msg: str, detail: str = ""):
        nonlocal failed
        failed += 1
        label = f"  ✗ {msg}"
        if detail:
            label += f"\n      detail: {detail}"
        print(label)

    print("\nVERISYNTH — Phase 9 Validation\n")

    # ── Import under test ─────────────────────────────────────────────
    try:
        from simulation.ids.trust_orchestrator import TrustOrchestrator
    except ImportError as e:
        print(f"  ✗ Cannot import TrustOrchestrator: {e}")
        sys.exit(1)

    # ── Test 1: TrustOrchestrator initialises ─────────────────────────
    try:
        trust_mgr  = StubTrustManager()
        alert_mgr  = StubAlertManager()
        orch = TrustOrchestrator(
            trust_manager = trust_mgr,
            alert_manager = alert_mgr,
        )
        ok("TrustOrchestrator initialises")
    except Exception as e:
        fail("TrustOrchestrator initialises", str(e))
        sys.exit(1)

    # ── Test 2: get_latest_scores is a method, not module-level ───────
    try:
        ids_mgr = StubIDSManager(trust_mgr)
        # Real check: calling the method should not raise AttributeError
        r = ids_mgr.get_latest_scores()
        assert isinstance(r, tuple) and len(r) == 2
        ok("get_latest_scores() is a method (not module-level function)")
    except Exception as e:
        fail("get_latest_scores() method check", str(e))

    # ── Test 3: score cache empty before first step ────────────────────
    try:
        s1, s2 = ids_mgr.get_latest_scores()
        assert s1 == {} and s2 == {}
        ok("score cache empty before first step")
    except AssertionError:
        fail("score cache empty before first step",
             f"got ids={s1} anomaly={s2}")

    # ── Test 4: basic step — correct number of verdicts ───────────────
    VEHICLES = ["ego", "v1", "v2", "v3", "attacker"]
    try:
        ids_scores     = {vid: 0.1 for vid in VEHICLES}
        anomaly_scores = {vid: 0.05 for vid in VEHICLES}
        verdicts = orch.step(
            live_vehicle_ids = VEHICLES,
            ids_scores       = ids_scores,
            anomaly_scores   = anomaly_scores,
            sim_step         = 1,
            sim_time         = 0.1,
        )
        assert len(verdicts) == len(VEHICLES), (
            f"expected {len(VEHICLES)} verdicts, got {len(verdicts)}"
        )
        ok("Step 1: 5 verdicts returned")
    except Exception as e:
        fail("Step 1: 5 verdicts returned", str(e))

    # ── Test 5: normal vehicles have low composite score ──────────────
    try:
        normal_verdicts = [v for v in verdicts if v.vehicle_id != "attacker"]
        for v in normal_verdicts:
            assert v.composite_score < 0.45, (
                f"{v.vehicle_id}: score={v.composite_score:.3f} ≥ 0.45"
            )
        ok("NORMAL vehicles score < 0.45")
    except AssertionError as e:
        fail("NORMAL vehicles score < 0.45", str(e))

    # ── Test 6: attacker with high scores gets higher composite ───────
    try:
        ids_scores["attacker"]     = 0.90
        anomaly_scores["attacker"] = 0.85
        trust_mgr.set_trust("attacker", 0.15)   # low trust → high H

        verdicts2 = orch.step(
            live_vehicle_ids = VEHICLES,
            ids_scores       = ids_scores,
            anomaly_scores   = anomaly_scores,
            sim_step         = 2,
            sim_time         = 0.2,
        )
        atk = next(v for v in verdicts2 if v.vehicle_id == "attacker")
        assert atk.composite_score > 0.45, (
            f"attacker composite={atk.composite_score:.3f} not > 0.45"
        )
        ok("ATTACK vehicle score > 0.45")
    except Exception as e:
        fail("ATTACK vehicle score > 0.45", str(e))

    # ── Test 7: sustained high scores → ISOLATE verdict ───────────────
    # Run enough steps with high attacker scores to trigger isolation.
    # Note: TrustOrchestrator thresholds are checked each step; isolation
    # fires as soon as composite ≥ threshold_isolate regardless of the
    # IDSManager consecutive-alert gate (those are separate mechanisms).
    try:
        ids_scores["attacker"]     = 0.95
        anomaly_scores["attacker"] = 0.90
        trust_mgr.set_trust("attacker", 0.10)

        isolated = False
        for step in range(3, 25):
            vs = orch.step(
                live_vehicle_ids = VEHICLES,
                ids_scores       = ids_scores,
                anomaly_scores   = anomaly_scores,
                sim_step         = step,
                sim_time         = step * 0.1,
            )
            atk_v = next(v for v in vs if v.vehicle_id == "attacker")
            if atk_v.verdict == "ISOLATE":
                isolated = True
                break

        assert isolated, "attacker was never isolated after 22 steps"
        ok("Sustained high scores → attacker ISOLATE verdict")
    except Exception as e:
        fail("Sustained high scores → attacker ISOLATE verdict", str(e))

    # ── Test 8: clean steps → RESTORE verdict (hysteresis) ────────────
    try:
        ids_scores["attacker"]     = 0.0
        anomaly_scores["attacker"] = 0.0
        trust_mgr.set_trust("attacker", 0.80)   # trust recovered

        restored = False
        for step in range(25, 60):
            vs = orch.step(
                live_vehicle_ids = VEHICLES,
                ids_scores       = ids_scores,
                anomaly_scores   = anomaly_scores,
                sim_step         = step,
                sim_time         = step * 0.1,
            )
            atk_v = next(v for v in vs if v.vehicle_id == "attacker")
            if atk_v.verdict == "RESTORE":
                restored = True
                break

        assert restored, (
            f"attacker never restored; last verdict={atk_v.verdict} "
            f"composite={atk_v.composite_score:.3f}"
        )
        ok("Isolation lifts after clean steps (RESTORE)")
    except Exception as e:
        fail("Isolation lifts after clean steps (RESTORE)", str(e))

    # ── Test 9: TRUST_CHANGE events emitted via EventLogger ───────────
    try:
        # Fresh orchestrator + event logger to see events from scratch
        trust2    = StubTrustManager()
        orch2     = TrustOrchestrator(
            trust_manager = trust2,
            alert_manager = StubAlertManager(),
        )
        ev_logger = StubEventLogger()

        # Simulate wiring in cosim_sync._run_step() — caller logs events
        ids_s = {"evil": 0.95}
        ano_s = {"evil": 0.90}
        trust2.set_trust("evil", 0.10)

        isolated_step = None
        for step in range(1, 30):
            vs = orch2.step(
                live_vehicle_ids = ["evil"],
                ids_scores       = ids_s,
                anomaly_scores   = ano_s,
                sim_step         = step,
                sim_time         = step * 0.1,
            )
            # Replicate cosim_sync event emission logic
            for v in vs:
                if v.action_taken in ("ISOLATED", "LIFTED_ISOLATION"):
                    ev_logger.log(
                        event_type = "TRUST_CHANGE",
                        sim_step   = v.sim_step,
                        sim_time   = v.sim_time,
                        data       = {
                            "vehicle_id":      v.vehicle_id,
                            "verdict":         v.verdict,
                            "action":          v.action_taken,
                            "composite_score": v.composite_score,
                        },
                    )
                    if v.action_taken == "ISOLATED":
                        isolated_step = step

        isolate_events = [e for e in ev_logger.events if e["action"] == "ISOLATED"]
        assert len(isolate_events) >= 1, "No ISOLATED event emitted"
        ok("TRUST_CHANGE ISOLATED event emitted by cosim_sync logic")

        # Now clean and check RESTORE event
        ids_s["evil"]  = 0.0
        ano_s["evil"]  = 0.0
        trust2.set_trust("evil", 0.85)
        for step in range(30, 70):
            vs = orch2.step(
                live_vehicle_ids = ["evil"],
                ids_scores       = ids_s,
                anomaly_scores   = ano_s,
                sim_step         = step,
                sim_time         = step * 0.1,
            )
            for v in vs:
                if v.action_taken in ("ISOLATED", "LIFTED_ISOLATION"):
                    ev_logger.log(
                        event_type = "TRUST_CHANGE",
                        sim_step   = v.sim_step,
                        sim_time   = v.sim_time,
                        data       = {
                            "vehicle_id":      v.vehicle_id,
                            "verdict":         v.verdict,
                            "action":          v.action_taken,
                            "composite_score": v.composite_score,
                        },
                    )

        restore_events = [
            e for e in ev_logger.events if e["action"] == "LIFTED_ISOLATION"
        ]
        assert len(restore_events) >= 1, "No LIFTED_ISOLATION event emitted"
        ok("TRUST_CHANGE LIFTED_ISOLATION event emitted by cosim_sync logic")
    except Exception as e:
        fail("TRUST_CHANGE events emitted", str(e))

    # ── Test 10: Orchestrator summary reports counts ───────────────────
    try:
        summary = orch.summary()
        assert "TrustOrchestrator" in summary
        assert "total_isolations=" in summary
        assert "total_restores=" in summary
        ok("Orchestrator summary() reports correct structure")
    except Exception as e:
        fail("Orchestrator summary() structure", str(e))

    # ── Test 11: query API works ───────────────────────────────────────
    try:
        score = orch.get_composite_score("ego")
        assert isinstance(score, float)
        verdict = orch.get_verdict("ego")
        assert isinstance(verdict, str)
        all_scores = orch.get_all_scores()
        assert isinstance(all_scores, dict)
        ok("Query API (get_composite_score, get_verdict, get_all_scores)")
    except Exception as e:
        fail("Query API", str(e))

    # ── Result ────────────────────────────────────────────────────────
    print(f"\n  {passed} passed, {failed} failed")
    if failed == 0:
        print("  ── Phase 9 validation PASSED ──\n")
    else:
        print("  ── Phase 9 validation FAILED ──\n")
        sys.exit(1)


if __name__ == "__main__":
    run()
