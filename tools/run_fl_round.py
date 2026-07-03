"""
VERISYNTH — FL Round Runner
Runs federated learning rounds using feature logs from simulation runs.

Usage:
    python tools/run_fl_round.py \
        --ids-config   configs/ids.yaml \
        --fl-config    configs/fl.yaml \
        --features     outputs/logs/ids_features_all.jsonl \
        --rounds       5
"""
import argparse, json, logging, os, sys
from pathlib import Path
from collections import Counter
import numpy as np
import torch
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulation.fl.coordinator import FLCoordinator
from simulation.fl.fl_client import FLClient
from simulation.fl.aggregator import FLAggregator
from simulation.fl.model_store import ModelStore
from simulation.ids.ids_manager import IDSManager
from simulation.ids.window_buffer import FEATURE_DIM, NUM_CLASSES, CLASS_NAMES

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S")
logger = logging.getLogger("verisynth.fl_runner")


def partition_features(
    features_path: str,
    n_clients:     int,
    seed:          int = 42,
):
    """
    Partition the feature dataset across simulated FL clients.
    Each client gets a non-overlapping subset of sequences.
    Returns list of (X, y) tuples.
    """
    import random
    rng = random.Random(seed)
    np.random.seed(seed)

    all_seqs = []
    with open(features_path) as f:
        for line in f:
            try:
                r = json.loads(line)
                seq = r.get("sequence")
                if seq is None: continue
                arr = np.array(seq, dtype=np.float32)
                if arr.ndim != 2 or arr.shape[-1] != FEATURE_DIM: continue
                all_seqs.append((arr, int(r.get("label", 0))))
            except: continue

    rng.shuffle(all_seqs)
    partitions = [[] for _ in range(n_clients)]
    for i, item in enumerate(all_seqs):
        partitions[i % n_clients].append(item)

    result = []
    for part in partitions:
        if not part:
            result.append((np.zeros((0, 20, FEATURE_DIM), dtype=np.float32),
                           np.zeros(0, dtype=np.int64)))
            continue
        X = np.stack([s[0] for s in part]).astype(np.float32)
        y = np.array([s[1] for s in part], dtype=np.int64)
        result.append((X, y))
    return result


class SimulatedFLClient(FLClient):
    """
    FL client with a local dataset (for offline FL simulation).
    Instead of pulling from live IDSManager window buffer,
    uses a pre-partitioned feature dataset.
    """

    def __init__(self, client_id, ids_manager, X, y, cfg):
        super().__init__(
            client_id    = client_id,
            ids_manager  = ids_manager,
            lr           = cfg["fl"]["client"]["learning_rate"],
            local_epochs = cfg["fl"]["client"]["local_epochs"],
            batch_size   = cfg["fl"]["client"]["batch_size"],
            min_samples  = cfg["fl"]["client"]["min_samples"],
        )
        self._X = X
        self._y = y

    def get_num_samples(self) -> int:
        return len(self._X)

    def local_train(self, round_id):
        """Override to use local dataset instead of window buffer."""
        if len(self._X) < self._min_samples:
            return None

        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        model  = self._ids._ml_detector.model
        device = self._ids._ml_detector._device

        optimizer = torch.optim.Adam(model.parameters(), lr=self._lr, weight_decay=1e-5)
        counts = Counter(self._y.tolist())
        total  = len(self._y)
        w = torch.zeros(NUM_CLASSES)
        for i in range(NUM_CLASSES):
            cnt = counts.get(i, 0)
            w[i] = min((total/(NUM_CLASSES*cnt)) if cnt>0 else 1.0, 50.0)
        criterion = nn.CrossEntropyLoss(weight=w.to(device))

        loader = DataLoader(
            TensorDataset(torch.from_numpy(self._X).float(),
                          torch.from_numpy(self._y).long()),
            batch_size=self._batch_size, shuffle=True,
        )

        model.train()
        losses, correct, total_n = [], 0, 0
        for _ in range(self._local_epochs):
            for xb, yb in loader:
                xb, yb = xb.to(device), yb.to(device)
                optimizer.zero_grad()
                _, logits, _ = model(xb)
                loss = criterion(logits, yb)
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                losses.append(loss.item())
                correct += (torch.argmax(logits,-1)==yb).sum().item()
                total_n += len(yb)

        from simulation.fl.fl_client import ClientUpdate
        return ClientUpdate(
            client_id  = self._id,
            round_id   = round_id,
            weights    = self.get_weights(),
            ae_weights = self.get_ae_weights(),
            n_samples  = len(self._X),
            train_loss = round(float(np.mean(losses)) if losses else 0.0, 4),
            train_acc  = round(correct/max(total_n,1), 4),
        )


def evaluate_global_model(ids_manager, features_path, max_records=2000):
    """Quick evaluation of global model on feature dataset."""
    from simulation.ids.window_buffer import NUM_CLASSES
    import torch

    all_seqs, all_labels = [], []
    with open(features_path) as f:
        for i, line in enumerate(f):
            if i >= max_records: break
            try:
                r    = json.loads(line)
                seq  = r.get("sequence")
                if seq is None: continue
                arr  = np.array(seq, dtype=np.float32)
                if arr.ndim != 2 or arr.shape[-1] != FEATURE_DIM: continue
                all_seqs.append(arr)
                all_labels.append(int(r.get("label", 0)))
            except: continue

    if not all_seqs:
        return {}

    X = torch.from_numpy(np.stack(all_seqs)).float()
    y = np.array(all_labels, dtype=np.int64)

    model  = ids_manager._ml_detector.model
    device = ids_manager._ml_detector._device
    model.eval()

    preds = []
    with torch.no_grad():
        for i in range(0, len(X), 256):
            xb = X[i:i+256].to(device)
            _, logits, _ = model(xb)
            preds.extend(torch.argmax(logits,-1).cpu().numpy())

    preds = np.array(preds)
    tp = int(np.sum((y!=0)&(preds!=0)))
    fp = int(np.sum((y==0)&(preds!=0)))
    tn = int(np.sum((y==0)&(preds==0)))
    fn = int(np.sum((y!=0)&(preds==0)))
    p  = tp/max(tp+fp,1)
    r  = tp/max(tp+fn,1)
    f1 = 2*p*r/max(p+r,1e-9)
    acc= (tp+tn)/max(tp+fp+tn+fn,1)
    return {
        "precision": round(p,4), "recall": round(r,4),
        "f1": round(f1,4), "accuracy": round(acc,4),
        "fpr": round(fp/max(fp+tn,1),4),
        "tp":tp,"fp":fp,"tn":tn,"fn":fn,
    }


def main():
    parser = argparse.ArgumentParser(description="VERISYNTH FL Round Runner")
    parser.add_argument("--ids-config",  default="configs/ids.yaml")
    parser.add_argument("--fl-config",   default="configs/fl.yaml")
    parser.add_argument("--features",    default="outputs/logs/ids_features_all.jsonl")
    parser.add_argument("--rounds",      type=int, default=None)
    parser.add_argument("--n-clients",   type=int, default=10)
    parser.add_argument("--strategy",    default=None,
                        choices=["fedavg","krum","trimmed_mean","median"])
    args = parser.parse_args()

    with open(args.fl_config) as f:
        fl_cfg = yaml.safe_load(f)
    with open(args.ids_config) as f:
        ids_cfg = yaml.safe_load(f)

    if args.rounds:
        fl_cfg["fl"]["rounds"]["total"] = args.rounds
    if args.strategy:
        fl_cfg["fl"]["aggregation"]["strategy"] = args.strategy

    n_rounds  = fl_cfg["fl"]["rounds"]["total"]
    n_clients = args.n_clients
    strategy  = fl_cfg["fl"]["aggregation"]["strategy"]

    logger.info("=== VERISYNTH Federated Learning ===")
    logger.info("Rounds: %d | Clients: %d | Strategy: %s",
                n_rounds, n_clients, strategy)
    logger.info("Features: %s", args.features)

    # Load and partition feature dataset
    partitions = partition_features(args.features, n_clients, seed=fl_cfg["fl"]["seed"])
    dist = Counter()
    for X, y in partitions:
        for label in y: dist[CLASS_NAMES[label]] += 1
    logger.info("Total partitioned sequences: %d | dist: %s",
                sum(len(X) for X,y in partitions), dict(dist))

    # Create one IDSManager per client (shared architecture, independent weights)
    # Override strategy in config
    fl_cfg["fl"]["aggregation"]["strategy"] = fl_cfg["fl"]["aggregation"].get("strategy", "fedavg")

    coordinator = FLCoordinator.from_config(args.fl_config)
    # Override aggregator strategy directly
    coordinator._aggregator._strategy = fl_cfg["fl"]["aggregation"]["strategy"]
    logger.info("Aggregation strategy: %s", coordinator._aggregator._strategy)

    ids_managers = []
    for i in range(n_clients):
        ids = IDSManager.from_config(args.ids_config, "configs/simulation.yaml")
        ids_managers.append(ids)
        X, y = partitions[i]
        client = SimulatedFLClient(f"vehicle_{i:03d}", ids, X, y, fl_cfg)
        coordinator.register_client(client)

    # Initialize global model from first client's pretrained weights
    coordinator.initialize_global_model(ids_managers[0])

    # Pre-round evaluation
    logger.info("--- Pre-FL evaluation ---")
    pre_metrics = evaluate_global_model(ids_managers[0], args.features)
    logger.info("Pre-FL | P=%.3f R=%.3f F1=%.3f FPR=%.4f",
        pre_metrics.get("precision",0), pre_metrics.get("recall",0),
        pre_metrics.get("f1",0), pre_metrics.get("fpr",0))

    # Run FL rounds
    all_metrics = [{"round_id": 0, "type": "pre_fl", **pre_metrics}]

    for r in range(1, n_rounds + 1):
        result = coordinator.run_round(r)
        if result.get("status") == "skipped":
            continue

        # Evaluate after each round
        eval_metrics = evaluate_global_model(ids_managers[0], args.features)
        result["eval"] = eval_metrics
        all_metrics.append({"round_id": r, "type": "fl_round", **eval_metrics})

        logger.info(
            "Round %d | P=%.3f R=%.3f F1=%.3f FPR=%.4f "
            "clients=%d/%d samples=%d",
            r,
            eval_metrics.get("precision",0),
            eval_metrics.get("recall",0),
            eval_metrics.get("f1",0),
            eval_metrics.get("fpr",0),
            result.get("n_updates",0),
            result.get("n_selected",0),
            result.get("total_samples",0),
        )

    # Save final aggregated model as pretrained
    final_weights = coordinator.global_weights
    if final_weights:
        from simulation.ids.model_utils import save_model
        ids_managers[0]._ml_detector.update_weights(final_weights)
        save_model(ids_managers[0]._ml_detector.model,
                   "outputs/models/local/cnn_lstm_pretrained.pt")
        logger.info("Final FL model saved as pretrained")

    # Print summary
    print("\n" + "═"*62)
    print(f"  VERISYNTH FL COMPLETE | {n_rounds} rounds | {n_clients} clients")
    print(f"  Strategy: {strategy}")
    print("═"*62)
    if len(all_metrics) >= 2:
        pre = all_metrics[0]
        post = all_metrics[-1]
        for m in ["precision","recall","f1","fpr"]:
            delta = post.get(m,0) - pre.get(m,0)
            sign  = "+" if delta >= 0 else ""
            print(f"  {m:15s}: {pre.get(m,0):.4f} → {post.get(m,0):.4f} "
                  f"({sign}{delta:.4f})")
    print("═"*62)

    out = Path("outputs/evaluation/fl_summary.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "config": {"rounds": n_rounds, "clients": n_clients, "strategy": strategy},
            "round_metrics": all_metrics,
        }, f, indent=2)
    logger.info("FL summary saved: %s", out)


if __name__ == "__main__":
    main()
