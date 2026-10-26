"""Camera-fault injectors (docs/06 §2). Each fault has severity 1..5 with documented parameters.

All injectors are pure OpenCV/numpy and deterministic given ``seed``. ``freeze`` and
``vibration`` are stateful (they need frame history / per-frame randomness).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# severity index 0 → severity 1
DRIFT_ROT_DEG = (0.5, 1.5, 3.0, 5.0, 8.0)
DRIFT_SHIFT_FRAC = (0.005, 0.01, 0.02, 0.04, 0.07)
VIB_AMPL_PX = (1.5, 3.0, 5.0, 9.0, 15.0)
HAZE_T = (0.82, 0.68, 0.55, 0.42, 0.3)
GLARE_RADIUS_FRAC = (0.08, 0.12, 0.17, 0.24, 0.33)
EXPOSURE_GAIN = (1.25, 1.45, 1.7, 2.0, 2.5)
CAST_GAIN = (1.06, 1.12, 1.2, 1.32, 1.5)
NOISE_SIGMA = (5.0, 9.0, 15.0, 23.0, 35.0)
OCCLUSION_AREA = (0.05, 0.12, 0.25, 0.5, 1.0)
SMUDGE_AREA = (0.05, 0.1, 0.16, 0.25, 0.38)
DEFOCUS_SIGMA = (1.0, 1.8, 2.8, 4.0, 6.0)

FAULTS = (
    "drift",
    "vibration",
    "haze",
    "condensation",
    "glare",
    "exposure",
    "color_cast",
    "ir_cut_stuck",
    "noise",
    "occlusion",
    "smudge",
    "spider_web",
    "defocus",
    "freeze",
    "dead",
)
# Which health check should catch each injected fault.
EXPECTED_CHECK = {
    "drift": "drift",
    "vibration": "vibration",
    "haze": "haze",
    "condensation": "haze",
    "glare": "glare",
    "exposure": "exposure",
    "color_cast": "color_cast",
    "ir_cut_stuck": "color_cast",
    "noise": "noise",
    "occlusion": "occlusion",
    "smudge": "smudge",
    "spider_web": "smudge",
    "defocus": "sharpness",
    "freeze": "freeze",
    "dead": "freeze",
}


def drift_matrix(
    w: int, h: int, severity: int, sign: int = 1, rot_deg: float | None = None, shift_frac: float | None = None
) -> np.ndarray:
    i = severity - 1
    rot = DRIFT_ROT_DEG[i] if rot_deg is None else rot_deg
    shift = DRIFT_SHIFT_FRAC[i] if shift_frac is None else shift_frac
    M = cv2.getRotationMatrix2D((w / 2, h / 2), sign * rot, 1.0)
    M[0, 2] += sign * shift * w
    M[1, 2] += 0.5 * shift * h
    return np.vstack([M, [0, 0, 1]]).astype(np.float64)


def warp(img: np.ndarray, H: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    return cv2.warpPerspective(img, H, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT101)


def _blob_mask(h: int, w: int, area: float, rng: np.random.Generator, soft: int = 0) -> np.ndarray:
    """Elliptical blob covering ~area of the frame at a random off-centre location."""
    if area >= 0.999:
        return np.full((h, w), 255, np.uint8)
    a = np.sqrt(area * h * w / np.pi)
    ax, ay = a * 1.3, a / 1.3
    cx = rng.uniform(ax * 0.6, w - ax * 0.6) if w > 1.2 * ax else w / 2
    cy = rng.uniform(ay * 0.6, h - ay * 0.6) if h > 1.2 * ay else h / 2
    m = np.zeros((h, w), np.uint8)
    cv2.ellipse(m, (int(cx), int(cy)), (int(ax), int(ay)), float(rng.uniform(0, 180)), 0, 360, 255, -1)
    if soft:
        m = cv2.GaussianBlur(m, (0, 0), soft)
    return m


@dataclass
class Fault:
    name: str
    severity: int
    seed: int = 0
    params: dict[str, float] = field(default_factory=dict)
    _frozen: np.ndarray | None = None
    _rng: np.random.Generator | None = None

    def __post_init__(self) -> None:
        if self.name not in FAULTS:
            raise ValueError(f"unknown fault {self.name}")
        if not 1 <= self.severity <= 5:
            raise ValueError("severity must be 1..5")
        self._rng = np.random.default_rng(self.seed)

    def apply(self, img: np.ndarray) -> np.ndarray:
        fn = getattr(self, f"_{self.name}")
        out: np.ndarray = fn(img)
        return out

    # --- injectors ------------------------------------------------------------------------
    def _drift(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        p = self.params
        return warp(img, drift_matrix(w, h, self.severity, int(p.get("sign", 1)), p.get("rot_deg"), p.get("shift_frac")))

    def _vibration(self, img: np.ndarray) -> np.ndarray:
        assert self._rng is not None
        h, w = img.shape[:2]
        a = VIB_AMPL_PX[self.severity - 1]
        dx, dy = self._rng.uniform(-a, a, 2)
        rot = self._rng.uniform(-a, a) * 0.05
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, 1.0)
        M[:, 2] += (dx, dy)
        return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT101)

    def _haze(self, img: np.ndarray) -> np.ndarray:
        t = HAZE_T[self.severity - 1]
        A = self.params.get("airlight", 215.0)
        return cv2.addWeighted(img, t, np.full_like(img, int(A)), 1 - t, 0)

    def _condensation(self, img: np.ndarray) -> np.ndarray:
        assert self._rng is not None
        h, w = img.shape[:2]
        t0 = HAZE_T[self.severity - 1]
        noise = self._rng.random((max(h // 64, 2), max(w // 64, 2))).astype(np.float32)
        field_ = cv2.resize(noise, (w, h), interpolation=cv2.INTER_CUBIC)
        field_ = cv2.GaussianBlur(field_, (0, 0), w / 30)
        field_ = (field_ - field_.min()) / max(float(np.ptp(field_)), 1e-6)
        t = (t0 + (1 - t0) * 0.6 * field_)[..., None]  # denser fog in some regions
        out = img.astype(np.float32) * t + 225.0 * (1 - t)
        return np.clip(out, 0, 255).astype(np.uint8)

    def _glare(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        rng = np.random.default_rng(self.seed)  # flare stays put across frames
        r = GLARE_RADIUS_FRAC[self.severity - 1] * np.hypot(w, h)
        cx, cy = rng.uniform(0.2 * w, 0.8 * w), rng.uniform(0.1 * h, 0.5 * h)
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        d = np.hypot(xx - cx, yy - cy) / r
        flare = np.clip(1.6 - d, 0, 1.6) ** 2 * 255
        out = img.astype(np.float32) + flare[..., None]
        return np.clip(out, 0, 255).astype(np.uint8)

    def _exposure(self, img: np.ndarray) -> np.ndarray:
        g = EXPOSURE_GAIN[self.severity - 1]
        if self.params.get("direction", 1) < 0:
            g = 1.0 / g
        return cv2.convertScaleAbs(img, alpha=g, beta=0)

    def _color_cast(self, img: np.ndarray) -> np.ndarray:
        g = CAST_GAIN[self.severity - 1]
        b, gch, r = cv2.split(img.astype(np.float32))
        # warm (orange) cast: R up, B down
        return cv2.merge([b / g, gch, r * g]).clip(0, 255).astype(np.uint8)

    def _ir_cut_stuck(self, img: np.ndarray) -> np.ndarray:
        g = CAST_GAIN[self.severity - 1]
        b, gch, r = cv2.split(img.astype(np.float32))
        return cv2.merge([b * g, gch / g, r * g]).clip(0, 255).astype(np.uint8)  # magenta

    def _noise(self, img: np.ndarray) -> np.ndarray:
        assert self._rng is not None
        n = self._rng.normal(0, NOISE_SIGMA[self.severity - 1], img.shape).astype(np.float32)
        return np.clip(img.astype(np.float32) + n, 0, 255).astype(np.uint8)

    def _occlusion(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        m = _blob_mask(h, w, OCCLUSION_AREA[self.severity - 1], np.random.default_rng(self.seed))
        out = img.copy()
        color = np.array(self.params.get("color", (35, 38, 40)), np.uint8)
        out[m > 0] = color
        return out

    def _smudge(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        rng = np.random.default_rng(self.seed)
        m = _blob_mask(h, w, SMUDGE_AREA[self.severity - 1], rng, soft=int(0.02 * w) + 1)
        alpha = (m.astype(np.float32) / 255.0)[..., None] * 0.9
        blurred = cv2.GaussianBlur(img, (0, 0), 3 + 2 * self.severity).astype(np.float32) * 1.05 + 8
        out = img.astype(np.float32) * (1 - alpha) + blurred * alpha
        return np.clip(out, 0, 255).astype(np.uint8)

    def _spider_web(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        rng = np.random.default_rng(self.seed)
        layer = np.zeros_like(img)
        cx, cy = int(w * 0.2), int(h * 0.2)
        n = 4 + 3 * self.severity
        for k in range(n):
            ang = 2 * np.pi * k / n
            r = rng.uniform(0.15, 0.35) * w
            p2 = (int(cx + r * np.cos(ang)), int(cy + r * np.sin(ang)))
            cv2.line(layer, (cx, cy), p2, (235, 235, 235), 1, cv2.LINE_AA)
        for ring in range(1, self.severity + 2):
            cv2.circle(layer, (cx, cy), int(ring * 0.04 * w), (220, 220, 220), 1, cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 0.8)
        return cv2.max(img, layer)

    def _defocus(self, img: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(img, (0, 0), DEFOCUS_SIGMA[self.severity - 1])

    def _freeze(self, img: np.ndarray) -> np.ndarray:
        if self._frozen is None:
            self._frozen = img.copy()
        return self._frozen

    def _dead(self, img: np.ndarray) -> np.ndarray:
        return np.full_like(img, int(self.params.get("level", 0)))


def inject(img: np.ndarray, name: str, severity: int, seed: int = 0, **params: float) -> np.ndarray:
    """One-shot convenience wrapper (stateless faults only)."""
    return Fault(name, severity, seed, dict(params)).apply(img)
