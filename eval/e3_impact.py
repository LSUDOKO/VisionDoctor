"""E3 — label-free AI-impact prediction (headline innovation).

(a) Leave-one-video-out grouped CV: Spearman ρ and MAE between predicted and actual agreement.
(b) MOT17 real labels: Spearman ρ between predicted drop and TRUE person AP@0.5 drop, per
    (video, fault, severity) group, using out-of-fold predictions only.
(c) Permutation importance. Then trains the final model on all data → models/impact_hgb.joblib.
"""

from __future__ import annotations

import csv
import json
import shutil

import numpy as np
from common import RESULTS, ROOT, bootstrap_ci, save
from scipy.stats import spearmanr
from sklearn.inspection import permutation_importance

from visiondoctor.impact.features import FEATURE_NAMES
from visiondoctor.impact.predictor import ImpactPredictor, model_path


def load() -> list[dict[str, str]]:
    with open(RESULTS / "impact" / "dataset.csv") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    rows = load()
    X = np.array([[float(r[f]) for f in FEATURE_NAMES] for r in rows])
    y = np.array([float(r["agreement"]) for r in rows])
    vids = np.array([r["video"] for r in rows])
    oof = np.zeros(len(y))
    folds = {}
    for v in sorted(set(vids)):
        te = vids == v
        m = ImpactPredictor().fit(X[~te], y[~te])
        oof[te] = m.predict(X[te])[0]
        rho = spearmanr(oof[te], y[te]).statistic
        folds[v] = {"n": int(te.sum()), "spearman": round(float(rho), 3),
                    "mae": round(float(np.mean(np.abs(oof[te] - y[te]))), 4)}
    rho_all = float(spearmanr(oof, y).statistic)
    idx = np.arange(len(y))
    rho_ci = bootstrap_ci(idx, fn=lambda i: spearmanr(oof[i.astype(int)], y[i.astype(int)]).statistic)

    # (b) true AP drop on MOT17 (held-out predictions), grouped by video × fault × severity
    groups: dict[tuple[str, str, str], list[int]] = {}
    for i, r in enumerate(rows):
        if r.get("ap_clean") not in (None, ""):
            groups.setdefault((r["video"], r["faults"], r["severity"]), []).append(i)
    pred_drop, true_drop, gkeys = [], [], []
    for k, ii in groups.items():
        apc = np.mean([float(rows[i]["ap_clean"]) for i in ii])
        apd = np.mean([float(rows[i]["ap_degraded"]) for i in ii])
        if apc <= 0.05:
            continue
        pred_drop.append(float(np.mean(1 - oof[ii])))
        true_drop.append(float((apc - apd) / apc))  # relative AP drop
        gkeys.append(k)
    rho_ap = float(spearmanr(pred_drop, true_drop).statistic) if len(pred_drop) > 2 else float("nan")
    gi = np.arange(len(pred_drop))
    pd_, td_ = np.array(pred_drop), np.array(true_drop)
    rho_ap_ci = bootstrap_ci(gi, fn=lambda i: spearmanr(pd_[i.astype(int)], td_[i.astype(int)]).statistic)

    # (c) final model + permutation importance
    final = ImpactPredictor().fit(X, y)
    final.version = f"hgb-{len(y)}rows"
    final.save(model_path())
    pi = permutation_importance(final.mean, X, y, n_repeats=5, random_state=7, n_jobs=1)
    imp = sorted(zip(FEATURE_NAMES, pi.importances_mean, strict=True), key=lambda t: -t[1])[:12]
    out = {
        "rows": len(y), "videos": sorted(set(vids)),
        "agreement_cv": {"spearman": round(rho_all, 3), "spearman_ci95": rho_ci,
                         "mae": round(float(np.mean(np.abs(oof - y))), 4), "per_video": folds},
        "true_ap_drop_mot17": {"groups": len(pred_drop), "spearman": round(rho_ap, 3), "spearman_ci95": rho_ap_ci,
                               "mae": round(float(np.mean(np.abs(pd_ - td_))), 4) if len(pd_) else None},
        "permutation_importance_top12": [{"feature": f, "importance": round(float(v), 4)} for f, v in imp],
        "model": final.version,
    }
    save("e3/impact.json", out)
    save("e3/scatter.json", {"agreement": {"pred": oof.round(4).tolist(), "true": y.round(4).tolist()},
                             "ap": {"pred_drop": pred_drop, "true_drop": true_drop, "groups": [list(k) for k in gkeys]}})
    final_dir = ROOT / "results" / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(model_path(), final_dir / "impact_hgb.joblib")
    print(json.dumps({k: out[k] for k in ("agreement_cv", "true_ap_drop_mot17")}, indent=1))


if __name__ == "__main__":
    main()
