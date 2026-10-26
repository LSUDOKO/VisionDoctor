"""Label-free target and labelled validation metrics.

``agreement``: F1@IoU0.5 between detections on a degraded frame and on the identical clean
frame (pseudo ground truth), per class group, conf ≥ 0.4 (docs/03 §6.3).
``average_precision``: VOC-style all-point AP@0.5 against real labels (MOT17), for validation.
"""

from __future__ import annotations

import numpy as np

from visiondoctor.impact.detector import GROUP, Detections

CONF = 0.4


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return np.asarray(inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-9))


def greedy_matches(pred: np.ndarray, scores: np.ndarray, gt: np.ndarray, thr: float = 0.5) -> np.ndarray:
    """Return a boolean TP flag per prediction (in descending-score order of ``scores``)."""
    order = np.argsort(-scores)
    iou = iou_matrix(pred[order], gt)
    used = np.zeros(len(gt), bool)
    tp = np.zeros(len(order), bool)
    for i in range(len(order)):
        if iou.shape[1] == 0:
            break
        cand = np.where(~used & (iou[i] >= thr))[0]
        if len(cand):
            j = cand[np.argmax(iou[i, cand])]
            used[j] = True
            tp[i] = True
    return tp


def _group(d: Detections, g: str) -> tuple[np.ndarray, np.ndarray]:
    k = np.array([GROUP.get(int(c)) == g for c in d.classes], bool) if len(d) else np.zeros(0, bool)
    return d.boxes[k], d.scores[k]


def agreement(degraded: Detections, clean: Detections, conf: float = CONF) -> float:
    """F1 of degraded detections against clean-frame detections, averaged over present groups."""
    deg, cln = degraded.filter(conf), clean.filter(conf)
    f1s = []
    for g in ("person", "vehicle"):
        pb, ps = _group(deg, g)
        gb, _ = _group(cln, g)
        if len(gb) == 0 and len(pb) == 0:
            continue
        tp = int(greedy_matches(pb, ps, gb).sum())
        prec = tp / max(len(pb), 1)
        rec = tp / max(len(gb), 1)
        f1s.append(0.0 if tp == 0 else 2 * prec * rec / (prec + rec))
    return float(np.mean(f1s)) if f1s else 1.0


def average_precision(preds: list[tuple[np.ndarray, np.ndarray]], gts: list[np.ndarray], thr: float = 0.5) -> float:
    """AP over a set of frames. ``preds`` = [(boxes, scores)], ``gts`` = [boxes]."""
    all_scores, all_tp = [], []
    n_gt = sum(len(g) for g in gts)
    for (pb, ps), gb in zip(preds, gts, strict=True):
        tp = greedy_matches(pb, ps, gb, thr)
        all_scores.append(np.sort(ps)[::-1])
        all_tp.append(tp)
    if n_gt == 0:
        return 1.0
    scores = np.concatenate(all_scores) if all_scores else np.zeros(0)
    tps = np.concatenate(all_tp) if all_tp else np.zeros(0, bool)
    order = np.argsort(-scores)
    tps = tps[order]
    ctp = np.cumsum(tps)
    cfp = np.cumsum(~tps)
    rec = ctp / n_gt
    prec = ctp / np.maximum(ctp + cfp, 1)
    mrec = np.concatenate([[0.0], rec, [1.0]])
    mpre = np.concatenate([[1.0], prec, [0.0]])
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))
