from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from visiondoctor.config import get_settings
from visiondoctor.privacy.face_blur import blur_faces, detect_faces

needs_model = pytest.mark.skipif(
    not (Path(get_settings().models_dir) / "yunet.onnx").exists(), reason="run scripts/download_models.sh"
)


def _face_image() -> np.ndarray:
    """A real face crop from OpenCV's YuNet example output (fetched with the model) or skip."""
    p = Path(get_settings().models_dir) / "face_sample.jpg"
    if not p.exists():
        pytest.skip("face sample missing")
    return cv2.imread(str(p))


@needs_model
def test_faces_are_blurred() -> None:
    img = _face_image()
    faces = detect_faces(img)
    assert len(faces) >= 1
    out, n = blur_faces(img)
    assert n >= len(faces)
    # After blurring no face should be detectable any more.
    assert len(detect_faces(out)) == 0


@needs_model
def test_no_faces_untouched() -> None:
    img = np.full((240, 320, 3), 120, np.uint8)
    out, n = blur_faces(img)
    assert n == 0 and np.array_equal(out, img)
