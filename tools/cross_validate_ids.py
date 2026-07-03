"""
VERISYNTH — IDS K-Fold Cross-Validation
Publication-quality evaluation for thesis.
"""
import argparse, json, logging, os, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from simulation.ids.window_buffer import FEATURE_DIM, NUM_CLASSES, CLASS_NAMES
from simulation.ids.cnn_lstm_model import CNNLSTMModel

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S")
logger = logging.getLogger("verisynth.crossval")


def load_features(path):
    X, y = [], []
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
                seq = r.get("sequence")
                if seq is None: continue
                arr = np.array(seq, dtype=np.float32)
                if arr.ndim != 2 or arr.shape[-1] != FEATURE_DIM: continue
                X.append(arr)
                y.append(int(r.get("label", 0)))
            except: continue
    return np.stack(X).astype(np.float32), np.array(y, dtype=np.int64)


def oversample(X, y, ratio=3, seed=42):
    np.random.seed(seed)
    counts = Counter(y.tolist())
    target = max(counts.values()) // ratio
    Xp, yp = [X], [y]
    for cls, cnt in counts.items():
        if cls == 0 or cnt >= target: continue
        idx = np.where(y==cls)[0]
        n   = target - cnt
        rep = np.random.choice(idx, size=n, replace=True)
        noise = np.random.normal(0, 0.01, X[rep].shape).astype(np.float32)
        Xp.append(np.clip(X[rep]+noise, 0, 1))
        yp.append(np.full(n, cls, dtype=np.int64))
    Xo = np.concatenate(Xp); yo = np.concatenate(yp)
    perm = np.random.permutation(len(Xo))
    return Xo[perm], yo[perm]


def compute_metrics(y_true, y_pred):
    tp = int(np.sum((y_true!=0)&(y_pred!=0)))
    fp = int(np.sum((y_true==0)&(y_pred!=0)))
    tn = int(np.sum((y_true==0)&(y_pred==0)))
    fn = int(np.sum((y_true!=0)&(y_pred==0)))
    p  = tp/max(tp+fp,1); r=tp/max(tp+fn,1)
    f1 = 2*p*r/max(p+r,1e-9)
    per = {}
    for i in range(NUM_CLASSES):
        tp_c=int(np.sum((y_true==i)&(y_pred==i)))
        fp_c=int(np.sum((y_true!=i)&(y_pred==i)))
        fn_c=int(np.sum((y_true==i)&(y_pred!=i)))
        pc=tp_c/max(tp_c+fp_c,1); rc=tp_c/max(tp_c+fn_c,1)
        f1c=2*pc*rc/max(pc+rc,1e-9)
        if tp_c+fn_c>0:
            per[CLASS_NAMES[i]]={"precision":round(pc,4),"recall":round(rc,4),
                                  "f1":round(f1c,4),"support":tp_c+fn_c}
    macro=float(np.mean([v["f1"] for v in per.values()]))
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,
            "precision":round(p,4),"recall":round(r,4),"f1":round(f1,4),
            "macro_f1":round(macro,4),"accuracy":round((tp+tn)/max(tp+fp+tn+fn,1),4),
            "fpr":round(fp/max(fp+tn,1),4),"per_class":per}


def train_fold(X_tr, y_tr, X_val, y_val, seq_len, device, epochs=20, bs=512):
    model = CNNLSTMModel(
        feature_dim=FEATURE_DIM, sequence_length=seq_len,
        cnn_channels=[32,64], cnn_kernel_size=3, cnn_padding=1,
        pool_kernel_size=2, lstm_hidden=128, lstm_layers=2,
        lstm_dropout=0.2, lstm_bidir=False, fc_hidden=64,
        dropout=0.3, num_classes=NUM_CLASSES,
    ).to(device)

    counts = Counter(y_tr.tolist())
    total  = len(y_tr)
    w = torch.zeros(NUM_CLASSES)
    for i in range(NUM_CLASSES):
        cnt=counts.get(i,0)
        w[i]=min((total/(NUM_CLASSES*cnt)) if cnt>0 else 1.0, 100.0)
    crit  = nn.CrossEntropyLoss(weight=w.to(device))
    opt   = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)

    X_bal, y_bal = oversample(X_tr, y_tr)
    tr_loader = DataLoader(TensorDataset(torch.from_numpy(X_bal).float(),
                                          torch.from_numpy(y_bal).long()),
                           batch_size=bs, shuffle=True)
    vl_loader = DataLoader(TensorDataset(torch.from_numpy(X_val).float(),
                                          torch.from_numpy(y_val).long()),
                           batch_size=bs)

    best_acc, best_state = 0.0, None
    for ep in range(1, epochs+1):
        model.train()
        for xb, yb in tr_loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            _, logits, _ = model(xb)
            crit(logits, yb).backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()
        model.eval()
        vc=vt=0
        with torch.no_grad():
            for xb,yb in vl_loader:
                xb,yb=xb.to(device),yb.to(device)
                _,logits,_=model(xb)
                vc+=(torch.argmax(logits,-1)==yb).sum().item(); vt+=len(yb)
        acc=vc/max(vt,1)
        if acc>=best_acc:
            best_acc=acc
            best_state={k:v.cpu().clone() for k,v in model.state_dict().items()}
        if ep % 5 == 0:
            logger.info("  Epoch %2d/%d | val_acc=%.3f", ep, epochs, acc)

    model.load_state_dict(best_state)
    model.eval()
    preds, trues = [], []
    with torch.no_grad():
        for xb,yb in vl_loader:
            _,logits,_=model(xb.to(device))
            preds.extend(torch.argmax(logits,-1).cpu().numpy())
            trues.extend(yb.numpy())
    return compute_metrics(np.array(trues), np.array(preds))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default="outputs/logs/ids_features_all.jsonl")
    parser.add_argument("--folds",    type=int, default=5)
    parser.add_argument("--epochs",   type=int, default=20)
    parser.add_argument("--output",   default="outputs/evaluation/cross_validation.json")
    args = parser.parse_args()

    from sklearn.model_selection import StratifiedKFold
    device = torch.device("cpu")

    logger.info("Loading: %s", args.features)
    X, y = load_features(args.features)
    logger.info("Dataset: %d sequences | dist: %s", len(X),
        {CLASS_NAMES[k]:v for k,v in sorted(Counter(y.tolist()).items())})

    seq_len = X.shape[1]
    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=42)
    fold_results = []

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y), 1):
        logger.info("=== Fold %d/%d (train=%d val=%d) ===",
                    fold, args.folds, len(tr_idx), len(val_idx))
        result = train_fold(X[tr_idx], y[tr_idx], X[val_idx], y[val_idx],
                            seq_len, device, epochs=args.epochs)
        fold_results.append(result)
        logger.info("Fold %d | P=%.3f R=%.3f F1=%.3f MacroF1=%.3f FPR=%.3f",
            fold, result["precision"], result["recall"],
            result["f1"], result["macro_f1"], result["fpr"])

    metrics = ["precision","recall","f1","macro_f1","accuracy","fpr"]
    summary = {}
    for m in metrics:
        vals = [r[m] for r in fold_results]
        summary[m] = {"mean":round(float(np.mean(vals)),4),
                      "std": round(float(np.std(vals)),4),
                      "min": round(float(np.min(vals)),4),
                      "max": round(float(np.max(vals)),4)}

    per_class_agg = defaultdict(lambda: defaultdict(list))
    for r in fold_results:
        for cls, mets in r["per_class"].items():
            for m,v in mets.items():
                if m != "support":
                    per_class_agg[cls][m].append(v)
    per_class_summary = {
        cls: {m: {"mean":round(float(np.mean(vals)),4),
                  "std": round(float(np.std(vals)),4)}
              for m,vals in mets.items()}
        for cls, mets in per_class_agg.items()
    }

    output = {
        "n_folds": args.folds, "n_sequences": len(X),
        "class_dist": {CLASS_NAMES[k]:v for k,v in sorted(Counter(y.tolist()).items())},
        "summary": summary, "per_class": per_class_summary,
        "fold_results": fold_results,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output,"w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "═"*62)
    print(f"  VERISYNTH IDS  {args.folds}-FOLD CROSS-VALIDATION")
    print("═"*62)
    for m in metrics:
        s = summary[m]
        print(f"  {m:15s}: {s['mean']:.4f} ± {s['std']:.4f}"
              f"  [{s['min']:.4f}, {s['max']:.4f}]")
    print("─"*62)
    print("  Per-class F1 (mean ± std):")
    for cls, mets in per_class_summary.items():
        f1 = mets.get("f1",{})
        print(f"    {cls:20s}: {f1.get('mean',0):.4f} ± {f1.get('std',0):.4f}")
    print("═"*62)
    print(f"  Saved: {args.output}")

if __name__ == "__main__":
    main()
