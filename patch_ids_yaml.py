"""
Patch configs/ids.yaml in-place.
Fixes three sections:
  1. ml.training: min_samples 99999→50, retrain_interval 99999→500
  2. trust: halved penalties, raised floor, faster recovery
  3. fusion: raise threshold_monitor from 0.45→0.55 to prevent
     AE-only signals from reaching MONITOR
"""
import yaml, pathlib, sys

path = pathlib.Path("configs/ids.yaml")
cfg  = yaml.safe_load(path.read_text())

# ── FIX-5: re-enable online training ─────────────────────────────────
t = cfg["ids"]["ml"]["training"]
t["min_samples"]            = 50
t["retrain_interval_steps"] = 500
t["local_epochs"]           = 3
print(f"Training: min_samples={t['min_samples']} interval={t['retrain_interval_steps']}")

# ── FIX-3/4: trust params ─────────────────────────────────────────────
cfg["ids"]["trust"] = {
    "init_trust":      0.70,
    "decay_rate":      0.0005,
    "recovery_rate":   0.010,
    "penalty_block":   0.15,
    "penalty_monitor": 0.05,
    "penalty_log":     0.01,
}
print("Trust: updated penalties and recovery")

# ── FIX-4: raise fusion monitor threshold ─────────────────────────────
# AE alone (weight 0.20 × conf≈1.0 = 0.20) must NOT reach MONITOR.
# ML alone (weight 0.40 × conf≈0.64 = 0.256) must NOT reach MONITOR.
# ML+AE    (0.40×0.64 + 0.20×1.0 = 0.456) must NOT reach MONITOR.
# → threshold_monitor raised to 0.50 requires rule or strong ML.
f = cfg["ids"]["fusion"]
f["threshold_monitor"] = 0.50
f["threshold_block"]   = 0.72
print(f"Fusion: threshold_monitor={f['threshold_monitor']} threshold_block={f['threshold_block']}")

path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
print("ids.yaml patched successfully")
