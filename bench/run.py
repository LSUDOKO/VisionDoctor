"""COOL benchmark harness (docs/05 §6): micro ops, end-to-end scan throughput, cost per 1M scans.

Same script on every configuration (A: COOL on c8g, B: stock OpenCV 5 on c8g, C: stock on x86,
or "local" for a developer machine). Inputs are frames from data/videos checked by SHA-256.
Prices come from the AWS Price List API at run time; nothing is hard-coded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def imds(path: str) -> str | None:
    try:
        req = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        tok = urllib.request.urlopen(req, timeout=0.5).read().decode()
        r = urllib.request.Request(f"http://169.254.169.254/latest/meta-data/{path}",
                                   headers={"X-aws-ec2-metadata-token": tok})
        return urllib.request.urlopen(r, timeout=0.5).read().decode()
    except Exception:  # noqa: BLE001 - not on EC2
        return None


def environment() -> dict[str, Any]:
    from visiondoctor import cv_runtime

    b = cv_runtime.build_info()
    return {
        "config": os.environ.get("VD_BENCH_CONFIG", "local"),
        "instance_type": imds("instance-type"),
        "region": (imds("placement/region") or None),
        "machine": platform.machine(), "kernel": platform.release(), "python": platform.python_version(),
        "cpu_count": os.cpu_count(), "cv2_version": cv2.__version__, "cv2_file": b["cv2_file"],
        "is_cool": b["is_cool"], "kleidicv_in_build_info": b["kleidicv"], "threads": cv2.getNumThreads(),
        "build_information": b["build_information"],
    }


def load_inputs() -> tuple[dict[str, np.ndarray], dict[str, str]]:
    from visiondoctor.sim import sources

    name = "MOT17-04" if sources.video_path("MOT17-04").exists() else "vtest"
    f = sources.read_frames(name, [300])[300]
    imgs = {"1080p": cv2.resize(f, (1920, 1080), interpolation=cv2.INTER_CUBIC),
            "4k": cv2.resize(f, (3840, 2160), interpolation=cv2.INTER_CUBIC)}
    sha = {k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in imgs.items()}
    return imgs, sha


def micro_ops(img: np.ndarray) -> dict[str, Any]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    H = cv2.getRotationMatrix2D((w / 2, h / 2), 3, 1.0)
    H = np.vstack([H, [0, 0, 1]])
    mx, my = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    mx += 1.5
    edges = cv2.Canny(gray, 50, 150)
    small = cv2.resize(gray, (w // 2, h // 2))
    p0 = cv2.goodFeaturesToTrack(small, 500, 0.01, 8)
    small2 = np.roll(small, 2, axis=1)
    orb = cv2.ORB_create(2000)
    k1, d1 = orb.detectAndCompute(small, None)
    k2, d2 = orb.detectAndCompute(small2, None)
    m = cv2.BFMatcher(cv2.NORM_HAMMING).match(d1, d2)
    src = np.float32([k1[x.queryIdx].pt for x in m]).reshape(-1, 1, 2)
    dst = np.float32([k2[x.trainIdx].pt for x in m]).reshape(-1, 1, 2)
    f32 = gray.astype(np.float32)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    return {
        "resize": lambda: cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA),
        "cvtColor": lambda: cv2.cvtColor(img, cv2.COLOR_BGR2LAB),
        "GaussianBlur": lambda: cv2.GaussianBlur(img, (0, 0), 3),
        "Laplacian": lambda: cv2.Laplacian(gray, cv2.CV_32F),
        "Sobel": lambda: cv2.Sobel(gray, cv2.CV_32F, 1, 0),
        "Canny": lambda: cv2.Canny(gray, 50, 150),
        "adaptiveThreshold": lambda: cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 15, 2),
        "morphologyEx": lambda: cv2.morphologyEx(gray, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)),
        "findContours": lambda: cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE),
        "warpPerspective": lambda: cv2.warpPerspective(img, H, (w, h)),
        "remap": lambda: cv2.remap(img, mx, my, cv2.INTER_LINEAR),
        "calcHist": lambda: cv2.calcHist([gray], [0], None, [256], [0, 256]),
        "filter2D": lambda: cv2.filter2D(f32, -1, k),
        "dft": lambda: cv2.dft(f32[:1024, :1024], flags=cv2.DFT_COMPLEX_OUTPUT),
        "calcOpticalFlowPyrLK": lambda: cv2.calcOpticalFlowPyrLK(small, small2, p0, None),
        "findHomography": lambda: cv2.findHomography(src, dst, cv2.USAC_MAGSAC, 3.0),
    }


def time_op(fn: Any, warmup: int, reps: int) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    med = statistics.median(ts)
    return {"median_ms": med, "p95_ms": float(np.percentile(ts, 95)),
            "cv": statistics.pstdev(ts) / max(statistics.mean(ts), 1e-9)}


def end_to_end(n_cams: int, scans: int) -> dict[str, Any]:
    from visiondoctor.health.checks.base import CameraState
    from visiondoctor.health.reference import learn_reference
    from visiondoctor.health.scan import scan
    from visiondoctor.sim.simulator import FleetSimulator

    sim = FleetSimulator(cameras=n_cams, width=1920, max_frames=12)  # bounded RAM at 1080p
    refs = {c: learn_reference(c, sim.calibration_frames(c, 20)) for c in sim.cameras}
    states = {c: CameraState() for c in sim.cameras}
    lat = []
    t0 = time.perf_counter()
    for i in range(scans):
        for c in sim.cameras:
            burst = [sim.clean_frame(c, t=i * 3 + k * 0.5) for k in range(5)]
            t = time.perf_counter()
            scan(c, burst, refs[c], states[c], now=float(i))
            lat.append((time.perf_counter() - t) * 1000)
    wall = time.perf_counter() - t0
    spm = 60.0 * len(lat) / wall
    return {"cameras": n_cams, "scans": len(lat), "scans_per_min": spm, "p50_ms": float(np.median(lat)),
            "p95_ms": float(np.percentile(lat, 95)),
            # Fleet capacity at 1 scan/camera/min for one process using all threads.
            "cameras_per_instance_at_1_scan_per_min": int(spm)}


def ec2_price(instance_type: str | None, region: str | None) -> float | None:
    if not instance_type:
        return None
    try:
        import boto3

        loc = {"us-east-1": "US East (N. Virginia)", "us-west-2": "US West (Oregon)"}.get(region or "us-east-1")
        pr = boto3.client("pricing", region_name="us-east-1")
        r = pr.get_products(ServiceCode="AmazonEC2", Filters=[
            {"Type": "TERM_MATCH", "Field": f, "Value": v} for f, v in {
                "instanceType": instance_type, "location": loc, "operatingSystem": "Linux", "tenancy": "Shared",
                "preInstalledSw": "NA", "capacitystatus": "Used"}.items()], MaxResults=1)
        item = json.loads(r["PriceList"][0])
        od = next(iter(item["terms"]["OnDemand"].values()))
        return float(next(iter(od["priceDimensions"].values()))["pricePerUnit"]["USD"])
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=50)
    ap.add_argument("--warmup", type=int, default=10)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--threads", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--cams", type=int, default=12)
    ap.add_argument("--scans", type=int, default=3)
    ap.add_argument("--cool-fee", type=float, default=None, help="COOL $/h from your Marketplace subscription page")
    args = ap.parse_args()
    cv2.setNumThreads(args.threads)
    env = environment()
    cfg = env["config"]
    out = ROOT / "results" / "bench" / cfg
    out.mkdir(parents=True, exist_ok=True)
    (out / "environment.json").write_text(json.dumps(env, indent=2))
    imgs, sha = load_inputs()
    runs = []
    for r in range(args.runs):
        micro = {res: {op: time_op(fn, args.warmup, args.reps) for op, fn in micro_ops(img).items()}
                 for res, img in imgs.items()}
        e2e = end_to_end(args.cams, args.scans)
        runs.append({"run": r, "micro": micro, "e2e": e2e})
        print(json.dumps({"run": r, "e2e": e2e}), flush=True)
    price = ec2_price(env["instance_type"], env["region"])
    spm = statistics.median(x["e2e"]["scans_per_min"] for x in runs)
    hourly = None if price is None else price + (args.cool_fee or 0.0)
    result = {"config": cfg, "inputs_sha256": sha, "threads": args.threads, "runs": runs,
              "ec2_usd_per_h": price, "cool_usd_per_h": args.cool_fee,
              "usd_per_1M_scans": None if hourly is None else hourly / (spm * 60) * 1e6,
              "env": {k: v for k, v in env.items() if k != "build_information"}}
    (out / "bench.json").write_text(json.dumps(result, indent=2))
    print("wrote", out / "bench.json")


if __name__ == "__main__":
    main()
