"""API smoke test with the local backend (no AWS, no auth)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from visiondoctor.config import get_settings


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("VD_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("VD_RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("VD_CAMERAS", "2")
    monkeypatch.setenv("VD_MONITOR", "0")
    get_settings.cache_clear()
    from visiondoctor.storage import get_storage

    get_storage.cache_clear()
    from visiondoctor.api.app import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()
    get_storage.cache_clear()


def test_health_reports_opencv5(client: TestClient) -> None:
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["opencv"].startswith("5.")


def test_fleet_flow(client: TestClient) -> None:
    cams = client.get("/api/cameras").json()
    assert len(cams) == 2
    cid = cams[0]["camera_id"]
    assert client.post("/api/sim/inject", json={"camera_id": cid, "fault": "occlusion", "severity": 4, "backdate_s": 10}).status_code == 200
    r = client.post(f"/api/cameras/{cid}/scan").json()
    assert r["faults"]
    detail = client.get(f"/api/cameras/{cid}").json()
    assert detail["latest_report"]["checks"]["occlusion"]["severity"] >= 2
    img = client.get(detail["images"]["current"])
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/cameras/{cid}/history").json()
    assert client.get("/api/summary").json()["cameras"] == 2
    assert "demo" in client.get("/api/scenarios").json()
