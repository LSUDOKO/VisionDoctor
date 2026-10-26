"""Record the real live console (CloudFront → Graviton4) for the video's website segment.
Logs phase timestamps so cut_web.py can trim each phase to its narration line."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
URL = "https://djekr86y464c8.cloudfront.net"
USER, PASS = os.environ["VD_JUDGE_USER"], os.environ["VD_JUDGE_PASS"]  # never hard-code credentials
TOKEN = os.environ["VD_TOKEN"]  # Cognito ID token for API reads


def api(path: str) -> object:
    req = urllib.request.Request(URL + path, headers={"Authorization": "Bearer " + TOKEN})
    return json.loads(urllib.request.urlopen(req).read())


def main() -> None:
    traces = api("/api/traces?limit=100")
    guard = next((t for t in traces if any(s["guard"].startswith("blocked") for s in t["steps"])), traces[0])
    cams = api("/api/cameras")
    cam = next((c["camera_id"] for c in cams if c.get("status") in ("degraded", "failed")), cams[0]["camera_id"])
    out = HERE / "build" / "web"
    out.mkdir(parents=True, exist_ok=True)
    marks: dict[str, float] = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=str(out),
                            record_video_size={"width": 1920, "height": 1080}, color_scheme="light")
        page = ctx.new_page()
        t0 = time.monotonic()
        mark = lambda k: marks.__setitem__(k, time.monotonic() - t0)  # noqa: E731
        page.goto(URL + "/#/login", wait_until="networkidle")
        page.fill("input[type=email]", USER)
        page.fill("input[type=password]", PASS)
        page.wait_for_timeout(600)
        mark("login_submit")
        page.click("button[type=submit]")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(out / "after_login.png"))
        if "fleet" not in page.url:
            page.goto(URL + "/#/fleet")
        page.wait_for_selector("[data-testid=camera-tile] img", timeout=30000)
        page.wait_for_timeout(1500)
        mark("fleet")
        page.wait_for_timeout(4500)
        page.mouse.move(400, 700)
        page.goto(f"{URL}/#/camera/{cam}")
        page.wait_for_selector("input[type=range]", timeout=20000)
        page.wait_for_timeout(2000)
        mark("camera")
        page.wait_for_timeout(1800)
        sl = page.locator("input[type=range]").first
        sl.scroll_into_view_if_needed()
        box = sl.bounding_box()
        if box:
            y = box["y"] + box["height"] / 2
            page.mouse.move(box["x"] + box["width"] * 0.5, y)
            page.mouse.down()
            for k in range(60):
                page.mouse.move(box["x"] + box["width"] * (0.5 - 0.42 * (k / 59)), y)
                page.wait_for_timeout(25)
            for k in range(80):
                page.mouse.move(box["x"] + box["width"] * (0.08 + 0.84 * (k / 79)), y)
                page.wait_for_timeout(25)
            page.mouse.up()
        page.wait_for_timeout(1500)
        mark("incidents")
        page.goto(URL + "/#/incidents")
        page.wait_for_timeout(4000)
        mark("trace")
        page.goto(f"{URL}/#/traces/{guard['trace_id']}")
        page.wait_for_timeout(2500)
        page.screenshot(path=str(HERE / "assets" / "trace_guard.png"))
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(3500)
        mark("end")
        ctx.close()
        b.close()
    vids = sorted(out.glob("*.webm"), key=lambda q: q.stat().st_mtime)
    (out / "marks.json").write_text(json.dumps({"video": str(vids[-1]), "marks": marks, "trace": guard["trace_id"], "camera": cam}, indent=1))
    print(json.dumps(marks, indent=1), vids[-1])


if __name__ == "__main__":
    main()
