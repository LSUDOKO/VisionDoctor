from __future__ import annotations

import numpy as np
import pytest

from visiondoctor.health.reference import Reference, learn_reference
from visiondoctor.sim.synthetic import SyntheticScene


@pytest.fixture(scope="session")
def scene_frames() -> list[np.ndarray]:
    return SyntheticScene(seed=1).frames(90)


@pytest.fixture(scope="session")
def reference(scene_frames: list[np.ndarray]) -> Reference:
    return learn_reference("cam-test", scene_frames[:60])


@pytest.fixture()
def burst(scene_frames: list[np.ndarray]) -> list[np.ndarray]:
    return scene_frames[60:75:3]
