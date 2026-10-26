"""Typed results shared by all health checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

CHECK_NAMES = (
    "sharpness",
    "drift",
    "vibration",
    "haze",
    "glare",
    "exposure",
    "occlusion",
    "smudge",
    "color_cast",
    "noise",
    "freeze",
)
# Faults whose score caps the overall health (docs/03 §3.12).
CRITICAL_CHECKS = ("drift", "occlusion", "freeze", "sharpness")
SOFTWARE_FIXABLE = ("drift", "exposure", "haze", "color_cast", "noise")


def band(value: float, edges: tuple[float, ...] | list[float]) -> int:
    """Severity 0..5 = number of ascending edges that ``value`` reaches."""
    return int(sum(value >= e for e in edges))


@dataclass
class CheckResult:
    name: str
    severity: int
    evidence: dict[str, Any] = field(default_factory=dict)
    region_mask: np.ndarray | None = None  # uint8 tile-grid mask (1 = affected)
    abstained: bool = False

    @property
    def score(self) -> float:
        return 1.0 - self.severity / 5.0

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "score": round(self.score, 3),
            "severity": self.severity,
            "evidence": _jsonable(self.evidence),
        }
        if self.abstained:
            d["abstained"] = True
        if self.region_mask is not None:
            d["region_tiles"] = int(self.region_mask.sum())
        return d


@dataclass
class HealthReport:
    camera_id: str
    ts: float
    checks: dict[str, CheckResult]
    overall_score: float
    heatmap: np.ndarray  # tile-grid float32 0..1 (1 = healthy)
    scan_ms: float
    reference_bucket: str
    op_ms: dict[str, float] = field(default_factory=dict)

    def faults(self, min_severity: int = 2) -> list[CheckResult]:
        return sorted(
            (c for c in self.checks.values() if c.severity >= min_severity),
            key=lambda c: -c.severity,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "ts": self.ts,
            "overall_score": round(self.overall_score, 3),
            "checks": {k: v.to_dict() for k, v in self.checks.items()},
            "heatmap": np.round(self.heatmap, 3).tolist(),
            "scan_ms": round(self.scan_ms, 1),
            "reference_bucket": self.reference_bucket,
            "op_ms": {k: round(v, 2) for k, v in self.op_ms.items()},
        }


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_jsonable(v) for v in x]
    if isinstance(x, np.ndarray):
        return np.round(x.astype(float), 4).tolist()
    if isinstance(x, np.floating):
        return round(float(x), 4)
    if isinstance(x, np.integer | np.bool_):
        return x.item()
    if isinstance(x, float):
        return round(x, 4)
    return x
