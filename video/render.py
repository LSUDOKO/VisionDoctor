"""Render index.html deterministically: Playwright (Chrome) → window.seek(t) → screenshot.

  python render.py stills                 # one key frame per narration line → build/stills/
  python render.py full --part 0/2        # frames for half the timeline → build/part0.mp4
Video: 60 fps output, 3 subframes per frame blended with ffmpeg tmix (motion blur).
"""

from __future__ import annotations

import argparse
import http.server
import json
import subprocess
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
FPS, SUB = 60, 3
PORT = 8765


def serve(port: int = PORT) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    handler.log_message = lambda *a, **k: None  # type: ignore[method-assign]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def open_page(p, port: int = PORT):  # noqa: ANN001, ANN201
    b = p.chromium.launch(channel="chrome", headless=True, args=["--disable-gpu-vsync", "--force-color-profile=srgb"])
    page = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    page.goto(f"http://127.0.0.1:{port}/index.html")
    total = page.evaluate("window.ready")
    return b, page, total


def stills() -> None:
    tl = json.loads((HERE / "timeline.json").read_text())
    out = HERE / "build/stills"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b, page, _ = open_page(p)
        for ln in tl["lines"]:
            t = ln["end"] - 0.2
            page.evaluate(f"window.seek({t})")
            page.screenshot(path=str(out / f"{ln['start']:06.1f}_{ln['id']}.jpg"), type="jpeg", quality=80)
        b.close()
    print("stills in", out)


def full(part: int, parts: int) -> None:
    tl = json.loads((HERE / "timeline.json").read_text())
    total = tl["total"]
    nframes = int(total * FPS)
    lo, hi = part * nframes // parts, (part + 1) * nframes // parts
    out = HERE / f"build/part{part}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS * SUB), "-c:v", "mjpeg",
                           "-i", "-", "-vf", f"tmix=frames={SUB}:weights='1 1 1',select='not(mod(n\\,{SUB}))',setpts=N/{FPS}/TB",
                           "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
                           str(out)], stdin=subprocess.PIPE)
    assert ff.stdin is not None
    with sync_playwright() as p:
        b, page, _ = open_page(p, PORT + 1 + part)
        for f in range(lo, hi):
            for s in range(SUB):
                t = (f + s / SUB) / FPS
                page.evaluate(f"window.seek({t:.5f})")
                ff.stdin.write(page.screenshot(type="jpeg", quality=92))
            if f % 600 == 0:
                print(f"part {part}: frame {f}/{hi}", flush=True)
        b.close()
    ff.stdin.close()
    ff.wait()
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stills", "full"])
    ap.add_argument("--part", default="0/1")
    a = ap.parse_args()
    if a.mode == "stills":
        serve()
        stills()
    else:
        i, n = map(int, a.part.split("/"))
        serve(PORT + 1 + i)
        full(i, n)
