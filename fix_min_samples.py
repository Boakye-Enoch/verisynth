"""
Minimal patch to configs/ids.yaml.
Only changes min_samples for both AE and CNN trainer.

Root cause: min_samples=50 but the window buffer only ever holds
23-38 active vehicle sequences at detection time, so training
NEVER fires and the AE threshold stays inf forever.

Fix: set min_samples=10 for both. This guarantees training runs
from the very first detection cycle (step 500, 23 vehicles tracked).
"""
import yaml, pathlib

path = pathlib.Path("configs/ids.yaml")
cfg  = yaml.safe_load(path.read_text())

# AE uses ids.ml.training.min_samples (same config block as CNN trainer)
before = cfg["ids"]["ml"]["training"]["min_samples"]
cfg["ids"]["ml"]["training"]["min_samples"] = 10
print(f"ml.training.min_samples: {before} → 10")

# Confirm other training values are sane
t = cfg["ids"]["ml"]["training"]
print(f"retrain_interval_steps: {t['retrain_interval_steps']}")
print(f"local_epochs:           {t['local_epochs']}")
print(f"batch_size:             {t['batch_size']}")

path.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))
print("\nids.yaml patched. Re-run: python main.py")
