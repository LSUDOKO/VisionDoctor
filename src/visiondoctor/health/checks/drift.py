"""Drift / displacement: ORB + USAC MAGSAC homography between reference and current background.

docs/03 §3.2. Matching runs on the median of the burst so moving people/cars are suppressed.
Severity bands are on mean corner displacement as a % of the frame diagonal.
"""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.health.checks.base import ScanContext
from visiondoctor.health.reference import orb
from visiondoctor.health.types import CheckResult, band
from visiondoctor.observability.metrics import timer

DISP_PCT_EDGES = (0.4, 0.8, 1.6, 3.2, 6.4)
MIN_INLIERS = 15
MIN_INLIER_RATIO = 0.25


def estimate_homography(
    ref_pts: np.ndarray, ref_des: np.ndarray, cur_gray: np.ndarray
) -> tuple[np.ndarray | None, int, int]:
    """Return (M mapping reference→current, n_good_matches, n_inliers).

    USAC MAGSAC homography selects inliers; the reported motion is a similarity (rotation,
    scale, translation) refit on those inliers with LMEDS. Camera drift is pan/tilt/roll, which
    a similarity captures well, and it does not extrapolate spurious shear/perspective to the
    frame corners when keypoints cluster in one part of the scene.
    """
    with timer("orb_detect"):
        kps, des = orb().detectAndCompute(cur_gray, None)
    if des is None or len(ref_des) < 8 or len(des) < 8:
        return None, 0, 0
    with timer("bf_match"):
        knn = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(ref_des, des, k=2)
    good = [p[0] for p in knn if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < MIN_INLIERS:
        return None, len(good), 0
    src = np.float32([ref_pts[m.queryIdx] for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kps[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    with timer("findHomography"):
        H, inl = cv2.findHomography(src, dst, cv2.USAC_MAGSAC, 3.0)
    if H is None or inl is None:
        return None, len(good), 0
    keep = inl.ravel().astype(bool)
    S, _ = cv2.estimateAffinePartial2D(src[keep], dst[keep], method=cv2.LMEDS)
    if S is None:
        return None, len(good), 0
    return np.vstack([S, [0.0, 0.0, 1.0]]), len(good), int(keep.sum())


def describe_homography(H: np.ndarray, w: int, h: int) -> dict[str, float]:
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    moved = cv2.perspectiveTransform(corners, H)
    disp = float(np.linalg.norm(moved - corners, axis=2).mean())
    return {
        "mean_corner_disp_px": disp,
        "disp_pct_diag": 100.0 * disp / float(np.hypot(w, h)),
        "rot_deg": float(np.degrees(np.arctan2(H[1, 0], H[0, 0]))),
        "tx": float(H[0, 2]),
        "ty": float(H[1, 2]),
    }


def check(ctx: ScanContext) -> CheckResult:
    bg = np.median(np.stack(ctx.frames), axis=0).astype(np.uint8) if len(ctx.frames) > 2 else ctx.frames[-1]
    gray = cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)
    H, n_good, n_inl = estimate_homography(ctx.bucket.kp_pts, ctx.bucket.descriptors, gray)
    h, w = gray.shape
    if H is None or n_inl < MIN_INLIERS:
        return CheckResult(
            "drift", 0, {"matches": n_good, "inliers": n_inl, "reason": "too_few_matches"}, abstained=True
        )
    ratio = n_inl / max(n_good, 1)
    ev: dict[str, object] = {"matches": n_good, "inliers": n_inl, "inlier_ratio": ratio}
    ev.update(describe_homography(H, w, h))
    ev["H"] = H
    sev = band(float(ev["disp_pct_diag"]), DISP_PCT_EDGES)  # type: ignore[arg-type]
    if ratio < MIN_INLIER_RATIO:
        ev["reason"] = "low_inlier_ratio_scene_change"
        sev = min(sev, 1)
    return CheckResult("drift", sev, ev)
