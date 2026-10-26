"""``visiondoctor`` command line: runtime info, simulator run, one-off scans, API server."""

from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    ap = argparse.ArgumentParser(prog="visiondoctor")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info", help="OpenCV / COOL runtime summary")
    sim = sub.add_parser("sim", help="run the fleet simulator with the monitor + agent (no API)")
    sim.add_argument("--cameras", type=int, default=12)
    sim.add_argument("--duration", type=float, default=60)
    sim.add_argument("--scenario", default="demo")
    sim.add_argument("--scan-interval", type=float, default=10)
    serve = sub.add_parser("serve", help="run the REST API (+ monitor)")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    if args.cmd == "info":
        from visiondoctor import cv_runtime

        print(json.dumps(cv_runtime.summary(), indent=2))
    elif args.cmd == "sim":
        run_sim(args.cameras, args.duration, args.scenario, args.scan_interval)
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run("visiondoctor.api.app:app", host=args.host, port=args.port)


def run_sim(cameras: int, duration: float, scenario: str, interval: float) -> None:
    import cv2

    from visiondoctor.config import get_settings
    from visiondoctor.fleet import Fleet
    from visiondoctor.observability.logging import setup
    from visiondoctor.service import FleetService
    from visiondoctor.sim.simulator import FleetSimulator

    setup()
    out = get_settings().results_dir / "sim" / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    sim = FleetSimulator(cameras=cameras, truth_path=out / "truth.jsonl")
    fleet = Fleet(sim)
    fleet.bootstrap()
    svc = FleetService(fleet, interval)
    sim.run_scenario(scenario)
    svc.start()
    t_end = time.time() + duration
    k = 0
    while time.time() < t_end:
        time.sleep(5)
        for cid in sim.cameras:  # snapshot frames so the run is inspectable
            cv2.imwrite(str(out / f"{cid}_{k:03d}.jpg"), sim.frame(cid))
        k += 1
    svc.stop()
    svc.agents.shutdown(wait=True)
    incs = fleet.store.query("incidents", limit=1000)
    summary = {"cameras": cameras, "duration_s": duration, "scenario": scenario, "truth_events": len(sim.events),
               "incidents": [{k: i[k] for k in ("camera_id", "fault_types", "state")} for i in incs]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
