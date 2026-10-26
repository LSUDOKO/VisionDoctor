"""Digital realignment: undo drift with the inverse of the reference→current transform."""

from __future__ import annotations

import cv2
import numpy as np

from visiondoctor.observability.metrics import timed


@timed("warpPerspective")
def apply(frame: np.ndarray, H: list[list[float]] | np.ndarray, analysis: bool = False) -> np.ndarray:
    """Undo drift. The downstream AI gets a black (cropped) border; health analysis gets a
    reflected border so the crop is not mistaken for an occlusion on later scans."""
    h, w = frame.shape[:2]
    Hinv = np.linalg.inv(np.asarray(H, dtype=np.float64))
    border = cv2.BORDER_REFLECT101 if analysis else cv2.BORDER_CONSTANT
    return cv2.warpPerspective(frame, Hinv, (w, h), flags=cv2.INTER_CUBIC, borderMode=border)


def params_from_drift(evidence: dict[str, object], scale: float = 1.0) -> dict[str, object]:
    """Repair parameters from drift evidence. ``scale`` maps working-res H to stream resolution."""
    H = np.asarray(evidence["H"], dtype=np.float64)
    if scale != 1.0:
        S = np.diag([scale, scale, 1.0])
        H = S @ H @ np.linalg.inv(S)
    return {
        "H": H.tolist(),
        "rot_deg": evidence.get("rot_deg", 0.0),
        "disp_pct_diag": evidence.get("disp_pct_diag", 0.0),
        "inlier_ratio": evidence.get("inlier_ratio", 0.0),
    }
