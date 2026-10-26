from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from visiondoctor.impact.agreement import agreement, average_precision, iou_matrix
from visiondoctor.impact.detector import Detections


def _dets(boxes: list[list[float]], cls: int = 0) -> Detections:
    b = np.array(boxes, float).reshape(-1, 4)
    return Detections(b, np.full(len(b), 0.9), np.full(len(b), cls, int))


def test_identical_detections_agree() -> None:
    d = _dets([[0, 0, 10, 10], [20, 20, 40, 50]])
    assert agreement(d, d) == 1.0


def test_missed_detections_lower_agreement() -> None:
    clean = _dets([[0, 0, 10, 10], [20, 20, 40, 50]])
    deg = _dets([[0, 0, 10, 10]])
    assert abs(agreement(deg, clean) - 2 / 3) < 1e-9


def test_empty_both_is_perfect() -> None:
    assert agreement(_dets([]), _dets([])) == 1.0


def test_ap_perfect_and_zero() -> None:
    gt = [np.array([[0, 0, 10, 10]], float)]
    assert average_precision([(gt[0], np.array([0.9]))], gt) == 1.0
    assert average_precision([(np.array([[50, 50, 60, 60]], float), np.array([0.9]))], gt) == 0.0


@given(st.lists(st.tuples(st.floats(0, 100), st.floats(0, 100), st.floats(1, 50), st.floats(1, 50)), max_size=8))
def test_iou_bounds(rects: list[tuple[float, float, float, float]]) -> None:
    b = np.array([[x, y, x + w, y + h] for x, y, w, h in rects], float).reshape(-1, 4)
    m = iou_matrix(b, b)
    assert np.all(m >= -1e-9) and np.all(m <= 1 + 1e-9)
    if len(b):
        assert np.allclose(np.diag(m), 1.0)
