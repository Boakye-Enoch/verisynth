"""
VERISYNTH — IDS Offline Trainer v4
Trains on EXACT feature vectors logged by the live IDS window buffer.
Usage:
    python tools/train_ids_offline.py \
        --features outputs/logs/ids_features.jsonl \
        --output   outputs/models/local/ \
        --epochs   30
"""
import argparse, json, logging, os, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml
from simulation.ids.window_buffer import FEATURE_DIM, NUM_CLASSES, CLASS_NAMES
from simulation.ids.cnn_lstm_model import CNNLSTMModel
from simulation.ids.anomaly_detector import TemporalAutoencoder
from simulation.ids.model_utils import save_model

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S")
logger = logging.getLogger("verisynth.train_ids_offline")


def load_feature_log(path: str) -> Tuple[np.ndarray, np.ndarray]:
    X_list, y_list, skipped = [], [], 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            seq = r.get("sequence")
            if seq is None:
                skipped += 1
                continue
            arr = np.array(seq, dtype=np.float32)
            if arr.ndim != 2 or arr.shape[-1] != FEATURE_DIM:
                skipped += 1
                continue
            X_list.append(arr)
            y_list.append(int(r.get("label", 0)))

    if skipped:
        logger.warning("Skipped %d malformed records", skipped)
    if not X_list:
        return np.zeros((0, 20, FEATURE_DIM), dtype=np.float32), np.zeros(0, dtype=np.int64)

    X = np.stack(X_list).astype(np.float32)
    y = np.array(y_list, dtype=np.int64)
    dist = {CLASS_NAMES[k]: v for k, v in sorted(Counter(y.tolist()).items())}
    logger.info("Loaded %d sequences | dist: %s", len(X), dist)
    return X, y


def oversample(X, y, ratio=3, seed=42):
    np.random.seed(seed)
    counts = Counter(y.tolist())
    target = max(counts.values()) // ratio
    Xp, yp = [X], [y]
    for cls, cnt in counts.items():
        if cls == 0 or cnt >= target:
            continue
        idx = np.where(y == cls)[0]
        rep = np.random.choice(idx, size=target - cnt, replace=True)
        noise = np.random.normal(0, 0.01, X[rep].shape).astype(np.float32)
        Xp.append(np.clip(X[rep] + noise, 0, 1))
        yp.append(np.full(target - cnt, cls, dtype=np.int64))
    Xo = np.concatenate(Xp)
    yo = np.concatenate(yp)
    perm = np.random.permutation(len(Xo))
    dist = {CLASS_NAMES[k]: v for k,v in sorted(Counter(yo.tolist()).items())}
    logger.info("After oversample: %d | dist: %s", len(Xo), dist)
    return Xo[perm], yo[perm]


def train_cnn_lstm(X, y, model, device, epochs=30, batch_size=512,
                   lr=0.001, val_frac=0.2, seed=42):
    torch.manual_seed(seed); np.random.seed(seed)
    perm = np.random.permutation(len(X))
    n_val = int(len(X) * val_frac)
    ti, vi = perm[n_val:], perm[:n_val]

    counts = Counter(y[ti].tolist())
    total  = len(ti)
    w = torch.zeros(NUM_CLASSES)
    for i in range(NUM_CLASSES):
        cnt = counts.get(i, 0)
        w[i] = min((total / (NUM_CLASSES * cnt)) if cnt > 0 else 1.0, 100.0)
    logger.info("Class weights: %s",
        {CLASS_NAMES[i]: round(float(w[i]),2) for i in range(NUM_CLASSES) if w[i]>0.01})

    crit = nn.CrossEntropyLoss(weight=w.to(device))
    opt  = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)

    def mkloader(idx, shuffle):
        ds = TensorDataset(torch.from_numpy(X[idx]).float(),
                           torch.from_numpy(y[idx]).long())
        return DataLoader(ds, batch_size=batch_size, shuffle=shuffle)

    tl = mkloader(ti, True)
    vl = mkloader(vi, False)
    best_acc, best_state = 0.0, None
    history = []

    for ep in range(1, epochs+1):
        model.train()
        losses, corr, tot = [], 0, 0
        for xb, yb in tl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            _, logits, _ = model(xb)
            loss = crit(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            losses.append(loss.item())
            corr += (torch.argmax(logits,-1)==yb).sum().item()
            tot  += len(yb)
        t_loss = float(np.mean(losses))
        t_acc  = corr / max(tot, 1)

        model.eval()
        vlosses, vc, vt = [], 0, 0
        cls_c: Dict[int,int] = defaultdict(int)
        cls_t: Dict[int,int] = defaultdict(int)
        with torch.no_grad():
            for xb, yb in vl:
                xb, yb = xb.to(device), yb.to(device)
                _, logits, _ = model(xb)
                vlosses.append(crit(logits, yb).item())
                preds = torch.argmax(logits,-1)
                vc += (preds==yb).sum().item()
                vt += len(yb)
                for gt, pr in zip(yb.cpu().numpy(), preds.cpu().numpy()):
                    cls_t[int(gt)] += 1
                    cls_c[int(gt)] += int(gt==pr)
        v_loss = float(np.mean(vlosses))
        v_acc  = vc / max(vt, 1)
        sched.step()

        per = {CLASS_NAMES[k]: round(cls_c[k]/max(cls_t[k],1),3)
               for k in sorted(cls_t) if cls_t[k]>0}
        logger.info("Epoch %2d/%d | tl=%.4f ta=%.3f vl=%.4f va=%.3f | %s",
            ep, epochs, t_loss, t_acc, v_loss, v_acc,
            " ".join(f"{k}={v:.2f}" for k,v in per.items()))
        history.append({"epoch":ep,"train_loss":round(t_loss,4),
            "train_acc":round(t_acc,4),"val_loss":round(v_loss,4),
            "val_acc":round(v_acc,4),"per_class":per})
        if v_acc >= best_acc:
            best_acc = v_acc
            best_state = {k: v.cpu().clone() for k,v in model.state_dict().items()}

    if best_state:
        model.load_state_dict(best_state)
        logger.info("Best restored | val_acc=%.3f", best_acc)
    return {"history": history, "best_val_acc": round(best_acc, 4)}


def train_ae(X, y, model, device, epochs=15, batch_size=512, sigma=3.0):
    idx = np.where(y==0)[0]
    logger.info("AE training on %d normal sequences", len(idx))
    Xn = X[idx]
    loader = DataLoader(TensorDataset(torch.from_numpy(Xn).float()),
                        batch_size=batch_size, shuffle=True)
    opt  = torch.optim.Adam(model.parameters(), lr=0.001)
    crit = nn.MSELoss()
    model.train()
    for ep in range(1, epochs+1):
        ls = []
        for (xb,) in loader:
            xb = xb.to(device)
            opt.zero_grad()
            loss = crit(model(xb), xb)
            loss.backward(); opt.step()
            ls.append(loss.item())
        logger.info("AE Epoch %2d/%d | loss=%.6f", ep, epochs, np.mean(ls))
    model.eval()
    with torch.no_grad():
        t = torch.from_numpy(Xn).float().to(device)
        errs = model.reconstruction_error(t).cpu().numpy()
    mean_e, std_e = float(np.mean(errs)), float(np.std(errs))
    thresh = mean_e + sigma * std_e
    logger.info("AE threshold | mean=%.6f std=%.6f thresh=%.6f", mean_e, std_e, thresh)
    return {"mean_error": mean_e, "std_error": std_e, "threshold": thresh}


def main():
    parser = argparse.ArgumentParser(description="VERISYNTH IDS Offline Trainer v4")
    parser.add_argument("--features", required=True,
        help="ids_features.jsonl from simulation run")
    parser.add_argument("--output",     default="outputs/models/local/")
    parser.add_argument("--epochs",     type=int,   default=30)
    parser.add_argument("--batch-size", type=int,   default=512)
    parser.add_argument("--config",     default="configs/ids.yaml")
    parser.add_argument("--seed",       type=int,   default=42)
    args = parser.parse_args()

    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    with open(args.config) as f:
        cfg = yaml.safe_load(f)
    m = cfg["ids"]["ml"]["model"]
    dev = torch.device("cpu")

    logger.info("=== VERISYNTH IDS Offline Trainer v4 (exact features) ===")

    if not Path(args.features).exists():
        logger.error("Feature log not found: %s — run simulation first", args.features)
        sys.exit(1)

    X, y = load_feature_log(args.features)
    if len(X) == 0:
        logger.error("No sequences loaded from feature log")
        sys.exit(1)

    raw_dist = {CLASS_NAMES[k]: v for k,v in sorted(Counter(y.tolist()).items())}
    logger.info("Raw distribution: %s", raw_dist)

    attack_count = sum(v for k,v in raw_dist.items() if k != "NORMAL")
    if attack_count == 0:
        logger.error("No attack sequences found — check attacks are enabled in simulation")
        sys.exit(1)

    X_bal, y_bal = oversample(X, y, ratio=3, seed=args.seed)
    seq_len = X.shape[1]
    logger.info("Sequence shape: %s", X.shape)

    model = CNNLSTMModel(
        feature_dim=FEATURE_DIM, sequence_length=seq_len,
        cnn_channels=m["cnn_channels"], cnn_kernel_size=m["cnn_kernel_size"],
        cnn_padding=m.get("cnn_padding",1), pool_kernel_size=m.get("pool_kernel_size",2),
        lstm_hidden=m["lstm_hidden_size"], lstm_layers=m["lstm_layers"],
        lstm_dropout=m.get("lstm_dropout",0.2), lstm_bidir=m.get("lstm_bidirectional",False),
        fc_hidden=m.get("fc_hidden",64), dropout=m["dropout"], num_classes=NUM_CLASSES,
    ).to(dev)
    logger.info("CNN-LSTM params: %d", model.count_parameters())

    result = train_cnn_lstm(X_bal, y_bal, model, dev,
                            epochs=args.epochs, batch_size=args.batch_size, seed=args.seed)
    cnn_path = str(out / "cnn_lstm_pretrained.pt")
    save_model(model, cnn_path)
    logger.info("CNN-LSTM saved | val_acc=%.3f", result["best_val_acc"])

    ae = TemporalAutoencoder(feature_dim=FEATURE_DIM, sequence_length=seq_len,
                             latent_dim=32, hidden_channels=64).to(dev)
    ae_r = train_ae(X, y, ae, dev, epochs=15, batch_size=args.batch_size)
    ae_path = str(out / "autoencoder_pretrained.pt")
    torch.save({"state_dict": ae.state_dict(), "threshold": ae_r["threshold"]}, ae_path)
    logger.info("AE saved | threshold=%.6f", ae_r["threshold"])

    with open(out / "offline_training_report.json", "w") as f:
        json.dump({"version":"v4","dataset":{"raw":len(X),"balanced":len(X_bal),
            "dist":raw_dist},"cnn_lstm":{**result,"path":cnn_path},
            "autoencoder":{**ae_r,"path":ae_path}}, f, indent=2)

    print(f"\n{'='*56}")
    print("  OFFLINE TRAINING v4 COMPLETE")
    print(f"{'='*56}")
    print(f"  Sequences:  {len(X_bal):,} (from {len(X):,} raw)")
    print(f"  Dist:       {raw_dist}")
    print(f"  CNN-LSTM:   val_acc={result['best_val_acc']:.4f}")
    print(f"  AE thresh:  {ae_r['threshold']:.6f}")
    print(f"  Saved:      {out}")
    print(f"{'='*56}\n")

if __name__ == "__main__":
    main()
