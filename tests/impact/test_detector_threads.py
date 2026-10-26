"""The shared detector must survive concurrent use (monitor thread + agent thread)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

from visiondoctor.config import get_settings

pytestmark = pytest.mark.skipif(not (Path(get_settings().models_dir) / "yolox.onnx").exists(), reason="models missing")


def test_concurrent_detect() -> None:
    from visiondoctor.impact.detector import get_detector

    det = get_detector()
    rng = np.random.default_rng(0)
    imgs = [rng.integers(0, 255, (360 + 40 * i, 640, 3), dtype=np.uint8) for i in range(4)]
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(det.detect, imgs * 4))
    assert len(results) == 16
