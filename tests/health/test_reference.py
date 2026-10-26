from __future__ import annotations

from pathlib import Path

import numpy as np

from visiondoctor.health.features import compute_features
from visiondoctor.health.reference import Reference, learn_reference


def test_reference_roundtrip(reference: Reference, tmp_path: Path) -> None:
    reference.save(tmp_path / "ref")
    r2 = Reference.load(tmp_path / "ref")
    assert r2.width == reference.width and set(r2.buckets) == set(reference.buckets)
    b1, b2 = reference.buckets["day"], r2.buckets["day"]
    assert np.array_equal(b1.descriptors, b2.descriptors)
    assert b1.glob_mean == b2.glob_mean


def test_static_keypoints_exist(reference: Reference) -> None:
    assert len(reference.buckets["day"].kp_pts) > 200
    assert reference.buckets["day"].activity > 0.5


def test_day_night_buckets(scene_frames: list[np.ndarray]) -> None:
    frames = scene_frames[:30] + [(f * 0.3).astype(np.uint8) for f in scene_frames[30:60]]
    ref = learn_reference("dn", frames)
    assert set(ref.buckets) == {"day", "night"}
    dark = compute_features(ref.prepare((scene_frames[70] * 0.3).astype(np.uint8)))
    assert ref.bucket_for(dark.glob["lum_median"])[0] == "night"


def test_ema_update_bumps_version(reference: Reference, scene_frames: list[np.ndarray]) -> None:
    v = reference.version
    reference.ema_update(compute_features(reference.prepare(scene_frames[80])))
    assert reference.version == v + 1
