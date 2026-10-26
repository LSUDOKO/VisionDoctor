from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from visiondoctor.agent.loop import AgentRunner
from visiondoctor.config import get_settings
from visiondoctor.fleet import Fleet
from visiondoctor.sim.simulator import FleetSimulator
from visiondoctor.storage.local import LocalStorage


@pytest.fixture()
def fleet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Fleet]:
    monkeypatch.setenv("VD_STATE_DIR", str(tmp_path))
    get_settings.cache_clear()
    sim = FleetSimulator(cameras=3, sources_list=["synthetic"], speed=1.0)
    for i, cam in enumerate(sim.cameras.values()):
        cam.criticality = 4 if i != 2 else 1
    f = Fleet(sim, LocalStorage(tmp_path))
    f.bootstrap()
    yield f
    get_settings.cache_clear()


@pytest.fixture()
def runner(fleet: Fleet) -> AgentRunner:
    return AgentRunner(fleet, agent="policy")


def open_incident(fleet: Fleet, cam: str, scans: int = 3) -> str:
    for _ in range(scans):
        r = fleet.scan_camera(cam)
        if r["incident_opened"]:
            return str(r["incident_opened"])
        inc = fleet.open_incident(cam)
        if inc:
            return str(inc["incident_id"])
    raise AssertionError(f"no incident opened on {cam}: {r}")
