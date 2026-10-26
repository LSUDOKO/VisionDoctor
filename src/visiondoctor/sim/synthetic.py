"""Procedural static-camera scene: textured buildings/pavement + moving "pedestrians".

Used by unit tests and as a fallback camera source when no footage has been downloaded.
"""

from __future__ import annotations

import cv2
import numpy as np


class SyntheticScene:
    def __init__(self, width: int = 640, height: int = 360, seed: int = 0, walkers: int = 6) -> None:
        rng = np.random.default_rng(seed)
        self.w, self.h = width, height
        bg = np.zeros((height, width, 3), np.uint8)
        bg[:] = (rng.integers(90, 140), rng.integers(100, 150), rng.integers(100, 150))
        for _ in range(40):  # buildings / signs
            x, y = int(rng.integers(0, width)), int(rng.integers(0, height))
            w, h = int(rng.integers(20, width // 4)), int(rng.integers(20, height // 3))
            color = tuple(int(c) for c in rng.integers(20, 235, 3))
            cv2.rectangle(bg, (x, y), (x + w, y + h), color, -1)
            for k in range(0, h, 8):  # windows / bricks
                cv2.line(bg, (x, y + k), (x + w, y + k), tuple(int(c * 0.7) for c in color), 1)
        for _ in range(60):
            p1 = (int(rng.integers(0, width)), int(rng.integers(0, height)))
            p2 = (int(rng.integers(0, width)), int(rng.integers(0, height)))
            cv2.line(bg, p1, p2, tuple(int(c) for c in rng.integers(0, 255, 3)), 1, cv2.LINE_AA)
        tex = rng.normal(0, 6, (height, width, 1)).astype(np.float32)
        self.bg = np.clip(bg.astype(np.float32) + tex, 0, 255).astype(np.uint8)
        self.walkers = [
            {
                "x": float(rng.uniform(0, width)),
                "y": float(rng.uniform(height * 0.4, height * 0.9)),
                "vx": float(rng.uniform(-6, 6)),
                "color": tuple(int(c) for c in rng.integers(30, 220, 3)),
            }
            for _ in range(walkers)
        ]
        self.t = 0
        self.rng = np.random.default_rng(seed + 1)

    def frame(self) -> np.ndarray:
        img = self.bg.copy()
        for wk in self.walkers:
            x = (wk["x"] + wk["vx"] * self.t) % self.w
            cv2.ellipse(img, (int(x), int(wk["y"])), (8, 22), 0, 0, 360, wk["color"], -1)
        noise = self.rng.normal(0, 1.5, img.shape).astype(np.float32)
        self.t += 1
        return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)

    def frames(self, n: int) -> list[np.ndarray]:
        return [self.frame() for _ in range(n)]
