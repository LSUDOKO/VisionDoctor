"""Bounded, reversible software repairs (docs/03 §4) applied as a per-camera correction profile.

The physical camera is never touched: the profile is applied to the stream before the
downstream AI. Each repair has parameter bounds enforced here and by the agent guard.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import cv2
import numpy as np

from visiondoctor.config import Settings, get_settings
from visiondoctor.health.reference import Reference
from visiondoctor.health.types import HealthReport
from visiondoctor.repair import dehaze, denoise, exposure, realign, white_balance

RepairType = Literal["realign", "exposure_fix", "dehaze", "white_balance", "denoise"]
REPAIR_FOR_FAULT: dict[str, RepairType] = {
    "drift": "realign",
    "exposure": "exposure_fix",
    "haze": "dehaze",
    "color_cast": "white_balance",
    "noise": "denoise",
}
FAULT_FOR_REPAIR = {v: k for k, v in REPAIR_FOR_FAULT.items()}

_APPLY: dict[str, Callable[..., np.ndarray]] = {
    "realign": lambda f, p: realign.apply(f, p["H"]),
    "exposure_fix": lambda f, p: exposure.apply(f, p["alpha"], p.get("gamma", 1.0), bool(p.get("clahe", False))),
    "dehaze": lambda f, p: dehaze.apply(f, p.get("omega", 0.9)),
    "white_balance": lambda f, p: white_balance.apply(f, p["gains"]),
    "denoise": lambda f, p: denoise.apply(f, p["h"]),
}


@dataclass
class RepairStep:
    type: RepairType
    params: dict[str, Any]
    repair_id: str = field(default_factory=lambda: "rp_" + uuid.uuid4().hex[:10])

    def apply(self, frame: np.ndarray) -> np.ndarray:
        return _APPLY[self.type](frame, self.params)


@dataclass
class CorrectionProfile:
    steps: list[RepairStep] = field(default_factory=list)

    def apply(self, frame: np.ndarray) -> np.ndarray:
        for s in self.steps:
            frame = s.apply(frame)
        return frame

    def without(self, repair_id: str) -> CorrectionProfile:
        return CorrectionProfile([s for s in self.steps if s.repair_id != repair_id])

    def to_list(self) -> list[dict[str, Any]]:
        return [{"repair_id": s.repair_id, "type": s.type, "params": s.params} for s in self.steps]


def check_bounds(repair: str, params: dict[str, Any], cfg: Settings | None = None) -> tuple[bool, str]:
    """Return (allowed, reason). Shared by the repair planner and the agent guard."""
    c = cfg or get_settings()
    if repair == "realign":
        rot = abs(float(params.get("rot_deg", 0.0)))
        disp = float(params.get("disp_pct_diag", 0.0)) / 100.0
        inl = float(params.get("inlier_ratio", 1.0))
        if rot > c.max_realign_rot_deg:
            return False, f"rotation {rot:.1f}° exceeds {c.max_realign_rot_deg}°"
        if disp > c.max_realign_disp_frac:
            return False, f"corner displacement {disp:.1%} of diagonal exceeds {c.max_realign_disp_frac:.0%}"
        if inl < c.min_realign_inlier_ratio:
            return False, f"inlier ratio {inl:.2f} below {c.min_realign_inlier_ratio}"
        H = params.get("H")
        if H is None or np.asarray(H).shape != (3, 3) or abs(np.linalg.det(np.asarray(H))) < 1e-6:
            return False, "homography missing or singular"
    elif repair == "exposure_fix":
        g = float(params.get("gamma", 1.0))
        a = float(params.get("alpha", 1.0))
        lo, hi = c.gamma_range
        if not lo <= g <= hi:
            return False, f"gamma {g:.2f} outside [{lo}, {hi}]"
        alo, ahi = c.exposure_gain_range
        if not alo <= a <= ahi:
            return False, f"gain {a:.2f} outside [{alo}, {ahi}]"
    elif repair == "dehaze":
        if float(params.get("omega", 0.9)) > c.max_dehaze_omega:
            return False, f"omega exceeds {c.max_dehaze_omega}"
    elif repair == "white_balance":
        lo, hi = c.wb_gain_range
        gains = params.get("gains", [])
        if len(gains) != 3 or not all(lo <= float(g) <= hi for g in gains):
            return False, f"gains {gains} outside [{lo}, {hi}]"
    elif repair == "denoise":
        if not 0 < float(params.get("h", 0)) <= c.max_denoise_h:
            return False, f"h outside (0, {c.max_denoise_h}]"
    else:
        return False, f"unknown repair {repair}"
    return True, "ok"


def plan(fault: str, report: HealthReport, reference: Reference) -> RepairStep | None:
    """Derive repair parameters from the scan evidence for a software-fixable fault."""
    rtype = REPAIR_FOR_FAULT.get(fault)
    if rtype is None:
        return None
    ev = report.checks[fault].evidence
    _, bucket = reference.bucket_for(0 if report.reference_bucket == "night" else 255)
    if rtype == "realign":
        if "H" not in ev:
            return None
        return RepairStep("realign", realign.params_from_drift(ev))
    if rtype == "exposure_fix":
        a = exposure.gain_for(float(ev["mean_lum"]), float(ev["ref_lum"]))
        return RepairStep("exposure_fix", {"alpha": round(a, 3), "gamma": 1.0, "clahe": False})
    if rtype == "dehaze":
        omega = min(0.95, 0.55 + 0.1 * report.checks[fault].severity)
        return RepairStep("dehaze", {"omega": round(omega, 2)})
    if rtype == "white_balance":
        b, g, r, _ = cv2.mean(bucket.background)
        return RepairStep("white_balance", {"ref_bgr_mean": [b, g, r], "gains": None})
    if rtype == "denoise":
        # Temporal σ is truncated at large noise, so take the larger of the two excess estimates.
        ex_t = float(ev.get("temporal_sigma", 0.0)) ** 2 - float(ev.get("ref_temporal_sigma", 0.0)) ** 2
        ex_s = float(ev.get("sigma", 0.0)) ** 2 - float(ev.get("ref_sigma", 0.0)) ** 2
        excess = math.sqrt(max(ex_t, ex_s, 1.0))
        return RepairStep("denoise", {"h": round(denoise.h_for(excess), 2)})
    return None


def finalize(step: RepairStep, frame: np.ndarray) -> RepairStep:
    """Resolve parameters that need a live frame (white-balance gains)."""
    if step.type == "white_balance" and step.params.get("gains") is None:
        step.params["gains"] = [round(g, 4) for g in white_balance.gains_for(frame, step.params["ref_bgr_mean"])]
    return step
