"""Per-frame image statistics shared by reference learning and checks.

All tile maps are computed with whole-image OpenCV filters followed by an INTER_AREA resize
to the tile grid, which equals block averaging — one pass per metric instead of 64 crops.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import cv2
import numpy as np

from visiondoctor.observability.metrics import timer

IMMERKAER_K = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)
DARK_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
TILE_METRICS = ("sharp_n", "lap_var", "tenengrad", "edge", "lum", "contrast", "dark", "sat", "lab_a", "lab_b", "entropy")


def resize_to_width(img: np.ndarray, width: int) -> np.ndarray:
    h, w = img.shape[:2]
    if w == width:
        return img
    interp = cv2.INTER_AREA if w > width else cv2.INTER_LINEAR
    with timer("resize"):
        return cv2.resize(img, (width, round(h * width / w)), interpolation=interp)


def _block_mean(m: np.ndarray, g: int) -> np.ndarray:
    return cv2.resize(m, (g, g), interpolation=cv2.INTER_AREA).astype(np.float64)


def immerkaer_sigma(gray: np.ndarray) -> float:
    """Fast noise std estimate (Immerkaer 1996)."""
    with timer("filter2D"):
        conv = cv2.filter2D(gray.astype(np.float32), -1, IMMERKAER_K)
    h, w = gray.shape
    return float(np.sqrt(np.pi / 2.0) * np.abs(conv[1:-1, 1:-1]).sum() / (6.0 * (w - 2) * (h - 2)))


def hf_ratio(gray: np.ndarray, r_frac: float = 0.15) -> float:
    """Share of spectral energy outside radius r_frac·N on a centered square crop."""
    h, w = gray.shape
    n = min(512, h, w)
    y0, x0 = (h - n) // 2, (w - n) // 2
    crop = gray[y0 : y0 + n, x0 : x0 + n].astype(np.float32)
    with timer("dft"):
        spec = cv2.dft(crop, flags=cv2.DFT_COMPLEX_OUTPUT)
    mag2 = spec[..., 0] ** 2 + spec[..., 1] ** 2
    mag2 = np.fft.fftshift(mag2)
    yy, xx = np.ogrid[:n, :n]
    rr = np.hypot(yy - n / 2, xx - n / 2)
    total = float(mag2.sum()) - float(mag2[n // 2, n // 2])  # drop DC
    if total <= 0:
        return 0.0
    return float(mag2[rr > r_frac * n].sum() / total)


def glare_mask(hsv: np.ndarray) -> np.ndarray:
    m = cv2.inRange(hsv, (0, 0, 250), (180, 40, 255))
    with timer("morphologyEx"):
        return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def dark_channel(img: np.ndarray, kernel: np.ndarray = DARK_KERNEL) -> np.ndarray:
    b, g, r = cv2.split(img)
    with timer("erode"):
        return cv2.erode(cv2.min(cv2.min(b, g), r), kernel)


def thumb_hash(gray: np.ndarray) -> str:
    t = cv2.resize(gray, (64, 36), interpolation=cv2.INTER_AREA)
    return hashlib.md5(t.tobytes()).hexdigest()


@dataclass
class FrameFeatures:
    tiles: dict[str, np.ndarray]
    glob: dict[str, float]
    gray: np.ndarray
    thumb: str
    extras: dict[str, np.ndarray] = field(default_factory=dict)


def compute_features(img: np.ndarray, grid: int = 8) -> FrameFeatures:
    """Compute all tile + global statistics for a BGR uint8 frame (already at working size)."""
    with timer("cvtColor"):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    g32 = gray.astype(np.float32)
    with timer("Laplacian"):
        lap = cv2.Laplacian(g32, cv2.CV_32F)
    with timer("Sobel"):
        gx = cv2.Sobel(g32, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g32, cv2.CV_32F, 0, 1, ksize=3)
    with timer("Canny"):
        edges = cv2.Canny(gray, 50, 150)
    dc = dark_channel(img)

    lap_m = _block_mean(lap, grid)
    lap_var = np.maximum(_block_mean(lap * lap, grid) - lap_m**2, 0.0)
    g_m = _block_mean(g32, grid)
    contrast = np.sqrt(np.maximum(_block_mean(g32 * g32, grid) - g_m**2, 0.0))

    h, w = gray.shape
    th, tw = h // grid, w // grid
    entropy = np.zeros((grid, grid))
    with timer("calcHist"):
        for i in range(grid):
            for j in range(grid):
                tile = gray[i * th : (i + 1) * th, j * tw : (j + 1) * tw]
                hist = cv2.calcHist([tile], [0], None, [32], [0, 256]).ravel()
                p = hist / max(hist.sum(), 1.0)
                p = p[p > 0]
                entropy[i, j] = float(-(p * np.log2(p)).sum())

    tiles = {
        # Contrast-normalised sharpness: invariant to gain and to haze (both affine in intensity).
        "sharp_n": lap_var / (contrast**2 + 1.0),
        "lap_var": lap_var,
        "tenengrad": _block_mean(gx * gx + gy * gy, grid),
        "edge": _block_mean(edges, grid) / 255.0,
        "lum": g_m,
        "contrast": contrast,
        "dark": _block_mean(dc, grid),
        "sat": _block_mean(hsv[..., 1], grid),
        "lab_a": _block_mean(lab[..., 1], grid) - 128.0,
        "lab_b": _block_mean(lab[..., 2], grid) - 128.0,
        "entropy": entropy,
    }
    gm = glare_mask(hsv)
    with timer("calcHist"):
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel() / gray.size
    b, gch, r, _ = cv2.mean(img)
    gray_mean = (b + gch + r) / 3.0 + 1e-6
    gstd = float(gray.std())
    glob = {
        "sharp_n": float(lap.var()) / (gstd**2 + 1.0),
        "lap_var": float(lap.var()),
        "tenengrad": float(np.mean(gx * gx + gy * gy)),
        "hf_ratio": hf_ratio(gray),
        "edge": float(edges.mean() / 255.0),
        "lum": float(gray.mean()),
        "lum_median": float(np.median(hsv[..., 2])),
        "contrast": float(gray.std()),
        "dark": float(dc.mean()),
        "sat": float(hsv[..., 1].mean()),
        "lab_a": float(lab[..., 1].mean() - 128.0),
        "lab_b": float(lab[..., 2].mean() - 128.0),
        "noise": immerkaer_sigma(gray),
        "glare_frac": float(gm.mean() / 255.0),
        "clip_low": float(hist[:6].sum()),
        "clip_high": float(hist[250:].sum()),
        "grayworld_dev": float(max(abs(b - gray_mean), abs(gch - gray_mean), abs(r - gray_mean)) / gray_mean),
        "std": float(gray.std()),
    }
    return FrameFeatures(tiles=tiles, glob=glob, gray=gray, thumb=thumb_hash(gray), extras={"glare": gm})
