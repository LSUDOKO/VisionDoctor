"""E2 — false incidents on clean footage, with ablations (no hysteresis, no day/night buckets).

Every clean burst of every video is scanned in sequence (one CameraState per camera, like a
live deployment). An incident = a fault at severity ≥ 2 on `hysteresis` consecutive scans.
False incidents per camera-day are extrapolated at 1 scan/min (1440 scans/day). The day/night
ablation replays the same videos with alternating dark (night) segments.
"""

from __future__ import annotations

import numpy as np

from common import save

from visiondoctor.health.checks.base import CameraState
from visiondoctor.health.reference import learn_reference
from visiondoctor.health.scan import scan
from visiondoctor.sim import sources

STRIDE = 6  # frames between scan starts
NIGHT_GAIN = 0.3


def night(f: np.ndarray) -> np.ndarray:
    return (f.astype(np.float32) * NIGHT_GAIN).astype(np.uint8)


def run(video: str, day_night: bool, single_bucket: bool) -> dict[str, float]:
    import cv2

    ref_idx = list(range(0, 240, 4))
    calib = list(sources.read_frames(video, ref_idx).values())
    if day_night:
        calib = calib + [night(f) for f in calib]
    ref = learn_reference(video, calib)
    if single_bucket and "night" in ref.buckets:
        ref.buckets.pop("night")
    st = CameraState()
    faulty_scans, inc_h1, inc_h2, streak, k = 0, 0, 0, 0, 0
    cap = cv2.VideoCapture(str(sources.video_path(video)))
    window: list[np.ndarray] = []
    i = -1
    while True:
        ok, f = cap.read()
        if not ok:
            break
        i += 1
        window = (window + [f])[-13:]
        if i < 252 or (i - 252) % STRIDE or len(window) < 13:
            continue
        burst = window[0::3]
        if day_night and (k // 10) % 2 == 1:
            burst = [night(f) for f in burst]
        rep = scan(video, burst, ref, st, now=float(k * 60))
        k += 1
        bad = bool(rep.faults(2))
        faulty_scans += bad
        inc_h1 += bad
        streak = streak + 1 if bad else 0
        inc_h2 += streak == 2
    return {"scans": k, "faulty_scans": faulty_scans, "incidents_no_hysteresis": inc_h1, "incidents_hysteresis2": inc_h2,
            "false_incidents_per_cam_day_h2": round(inc_h2 / k * 1440, 2), "false_incidents_per_cam_day_h1": round(inc_h1 / k * 1440, 2)}


def main() -> None:
    out: dict[str, object] = {"stride_frames": STRIDE, "videos": {}}
    for v in sources.available():
        out["videos"][v] = {  # type: ignore[index]
            "day": run(v, day_night=False, single_bucket=False),
            "day_night_buckets": run(v, day_night=True, single_bucket=False),
            "day_night_single_ref": run(v, day_night=True, single_bucket=True),
        }
        print(v, out["videos"][v], flush=True)  # type: ignore[index]
    vids = out["videos"]  # type: ignore[assignment]
    for key in ("day", "day_night_buckets", "day_night_single_ref"):
        scans = sum(vids[v][key]["scans"] for v in vids)
        h2 = sum(vids[v][key]["incidents_hysteresis2"] for v in vids)
        h1 = sum(vids[v][key]["incidents_no_hysteresis"] for v in vids)
        out[f"pooled_{key}"] = {"scans": scans, "per_cam_day_h2": round(h2 / scans * 1440, 2),
                                "per_cam_day_h1": round(h1 / scans * 1440, 2)}
    save("e2/false_alarms.json", out)


if __name__ == "__main__":
    main()
