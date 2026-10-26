"""Impact regressor: health features → detector agreement (≈ fraction of clean accuracy kept).

HistGradientBoostingRegressor (OpenCV's ml module moved to contrib), plus 5%/95% quantile
models for a 90% interval. A per-camera offset calibrates predictions on clean frames to 1.0.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from visiondoctor.config import get_settings
from visiondoctor.health.reference import Reference
from visiondoctor.health.types import HealthReport
from visiondoctor.impact.detector import Detections, get_detector
from visiondoctor.impact.features import FEATURE_NAMES, detector_signals, feature_vector, top5_conf, top_deviations

SEED = 7


def _model(**kw: Any) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, random_state=SEED, **kw)


@dataclass
class ImpactPredictor:
    mean: HistGradientBoostingRegressor = field(default_factory=_model)
    lo: HistGradientBoostingRegressor = field(default_factory=lambda: _model(loss="quantile", quantile=0.05))
    hi: HistGradientBoostingRegressor = field(default_factory=lambda: _model(loss="quantile", quantile=0.95))
    version: str = "untrained"

    def fit(self, X: np.ndarray, y: np.ndarray) -> ImpactPredictor:
        self.mean.fit(X, y)
        self.lo.fit(X, y)
        self.hi.fit(X, y)
        return self

    def predict(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        X = np.atleast_2d(X)
        m = np.clip(self.mean.predict(X), 0, 1)
        lo = np.clip(np.minimum(self.lo.predict(X), m), 0, 1)
        hi = np.clip(np.maximum(self.hi.predict(X), m), 0, 1)
        return m, lo, hi

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"mean": self.mean, "lo": self.lo, "hi": self.hi, "version": self.version, "features": FEATURE_NAMES}, path)

    @classmethod
    def load(cls, path: Path) -> ImpactPredictor:
        d = joblib.load(path)
        if d["features"] != FEATURE_NAMES:
            raise ValueError("feature schema changed — retrain the impact model (make eval-impact)")
        return cls(d["mean"], d["lo"], d["hi"], d["version"])


_PRED: ImpactPredictor | None = None


def model_path() -> Path:
    return get_settings().models_dir / "impact_hgb.joblib"


def get_predictor() -> ImpactPredictor | None:
    global _PRED
    if _PRED is None and model_path().exists():
        _PRED = ImpactPredictor.load(model_path())
    return _PRED


def detector_baseline(frames: list[np.ndarray]) -> dict[str, float]:
    det = get_detector()
    ds = [det.detect(f) for f in frames]
    return {"count": float(np.mean([len(d.filter(0.4)) for d in ds])), "top5": float(np.mean([top5_conf(d) for d in ds]))}


def predict_impact(
    report: HealthReport, frames: list[np.ndarray], reference: Reference, dets: list[Detections] | None = None
) -> dict[str, Any]:
    """Predict accuracy kept (agreement) for the current burst. Falls back to a monotone
    heuristic of health severity if no trained model is available."""
    if dets is None:
        det = get_detector()
        dets = [det.detect(f) for f in frames[-3:]]
    base = reference.detector_baseline or {"count": 1.0, "top5": 0.5}
    sig = detector_signals(dets, base)
    x = feature_vector(report, sig)
    pred = get_predictor()
    if pred is None:
        worst = max((c.severity for c in report.checks.values()), default=0)
        m = lo = hi = max(0.0, 1.0 - 0.15 * worst)
        model = "heuristic"
    else:
        mm, ll, hh = pred.predict(x)
        off = float(base.get("calib_offset", 0.0))
        m, lo, hi = (float(np.clip(v[0] + off, 0, 1)) for v in (mm, ll, hh))
        model = pred.version
    return {
        "predicted_accuracy": round(m, 3),
        "predicted_drop": round(1 - m, 3),
        "ci90": [round(lo, 3), round(hi, 3)],
        "features_top3": top_deviations(x),
        "detector_signals": {k: round(v, 3) for k, v in sig.items()},
        "model": model,
    }
