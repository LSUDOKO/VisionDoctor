"""Merge results/bench/<config>/bench.json into summary.csv / summary.json (+ speedups vs A)."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "results" / "bench"


def main() -> None:
    res = {p.parent.name: json.loads(p.read_text()) for p in sorted(B.glob("*/bench.json"))}
    rows = []
    for cfg, r in res.items():
        for resol in r["runs"][0]["micro"]:
            for op in r["runs"][0]["micro"][resol]:
                med = statistics.median(run["micro"][resol][op]["median_ms"] for run in r["runs"])
                rows.append({"config": cfg, "res": resol, "op": op, "median_ms": round(med, 4)})
    with open(B / "summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["config", "res", "op", "median_ms"])
        w.writeheader()
        w.writerows(rows)
    summary = {
        "available": True,
        "configs": {c: {"instance_type": r["env"].get("instance_type"), "is_cool": r["env"]["is_cool"],
                        "cv2_version": r["env"]["cv2_version"], "threads": r["threads"],
                        "scans_per_min": statistics.median(x["e2e"]["scans_per_min"] for x in r["runs"]),
                        "scan_p50_ms": statistics.median(x["e2e"]["p50_ms"] for x in r["runs"]),
                        "scan_p95_ms": statistics.median(x["e2e"]["p95_ms"] for x in r["runs"]),
                        "usd_per_1M_scans": r.get("usd_per_1M_scans")} for c, r in res.items()},
        "ops": [{"op": f"{x['op']}@{x['res']}", "config": x["config"], "median_ms": x["median_ms"]} for x in rows],
    }
    if "A" in res:
        base = {(x["res"], x["op"]): x["median_ms"] for x in rows if x["config"] == "A"}
        summary["speedup_vs"] = {c: {f"{op}@{rs}": round(ms / base[(rs, op)], 2) for x in rows
                                     if x["config"] == c for rs, op, ms in [(x["res"], x["op"], x["median_ms"])]
                                     if base.get((rs, op))} for c in res if c != "A"}
    (B / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["configs"], indent=2))


if __name__ == "__main__":
    main()
