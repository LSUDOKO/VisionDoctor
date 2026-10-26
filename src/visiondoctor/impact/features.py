"""Runtime impact features: health-check outputs + detector self-signals (docs/03 §6.4).

Everything here is computable without labels on a live camera.
"""

from __future__ import annotations

import numpy as np

from visiondoctor.health.types import CHECK_NAMES, HealthReport
from visiondoctor.impact.detector import Detections

EVIDENCE_KEYS: list[tuple[str, str, float]] = [
    # (check, evidence key, default when absent)
    ("sharpness", "sharp_n_ratio", 1.0),
    ("sharpness", "tenengrad_ratio", 1.0),
    ("sharpness", "hf_ratio", 1.0),
    ("drift", "disp_pct_diag", 0.0),
    ("drift", "inlier_ratio", 1.0),
    ("vibration", "jitter_px", 0.0),
    ("haze", "contrast_loss", 0.0),
    ("haze", "dark_delta_rel", 0.0),
    ("haze", "saturation_ratio", 1.0),
    ("glare", "delta_frac", 0.0),
    ("glare", "largest_blob_frac", 0.0),
    ("exposure", "lum_delta_rel", 0.0),
    ("exposure", "clip_low", 0.0),
    ("exposure", "clip_high", 0.0),
    ("occlusion", "occluded_frac", 0.0),
    ("smudge", "smudged_frac", 0.0),
    ("smudge", "candidate_tiles", 0.0),
    ("color_cast", "lab_dist", 0.0),
    ("noise", "ratio", 1.0),
    ("freeze", "frozen", 0.0),
    ("freeze", "dead", 0.0),
]
DETECTOR_KEYS = ["det_count_ratio", "det_conf_ratio", "det_conf_entropy"]
FEATURE_NAMES = (
    [f"sev_{c}" for c in CHECK_NAMES]
    + [f"{c}.{k}" for c, k, _ in EVIDENCE_KEYS]
    + ["overall"]
    + DETECTOR_KEYS
)


def top5_conf(d: Detections) -> float:
    s = np.sort(d.scores)[::-1][:5]
    return float(s.mean()) if len(s) else 0.0


def detector_signals(dets: list[Detections], baseline: dict[str, float]) -> dict[str, float]:
    counts = [len(d.filter(0.4)) for d in dets]
    confs = [top5_conf(d) for d in dets]
    all_scores = np.concatenate([d.scores for d in dets]) if dets else np.zeros(0)
    hist, _ = np.histogram(all_scores, bins=10, range=(0, 1))
    p = hist / max(hist.sum(), 1)
    p = p[p > 0]
    return {
        "det_count_ratio": float(np.mean(counts)) / max(baseline.get("count", 1.0), 0.5),
        "det_conf_ratio": float(np.mean(confs)) / max(baseline.get("top5", 0.5), 0.05),
        "det_conf_entropy": float(-(p * np.log2(p)).sum()),
    }


def feature_vector(report: HealthReport, det_sig: dict[str, float]) -> np.ndarray:
    v: list[float] = [float(report.checks[c].severity) if c in report.checks else 0.0 for c in CHECK_NAMES]
    for c, k, default in EVIDENCE_KEYS:
        r = report.checks.get(c)
        val = r.evidence.get(k, default) if r is not None else default
        v.append(float(val) if isinstance(val, int | float | bool) and val is not None else default)
    v.append(report.overall_score)
    v.extend(det_sig.get(k, 1.0) for k in DETECTOR_KEYS)
    return np.asarray(v, dtype=np.float64)


# Feature values of a perfectly healthy camera; used to explain which inputs moved.
CLEAN_VECTOR = np.asarray(
    [0.0] * len(CHECK_NAMES) + [d for _, _, d in EVIDENCE_KEYS] + [1.0, 1.0, 1.0, 0.0], dtype=np.float64
)


def top_deviations(x: np.ndarray, k: int = 3) -> list[str]:
    scale = np.maximum(np.abs(CLEAN_VECTOR), 1.0)
    dev = np.abs(x - CLEAN_VECTOR) / scale
    dev[FEATURE_NAMES.index("det_conf_entropy")] = 0.0  # not interpretable on its own
    return [FEATURE_NAMES[i] for i in np.argsort(-dev)[:k] if dev[i] > 0.05]
