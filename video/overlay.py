"""Composite real-world inserts (stock hardware clips, AWS console screenshots, CloudWatch widgets)
onto the rendered video without re-rendering it: build/video_nosound.mp4 -> build/video_overlaid.mp4.

Each insert is a framed card (cream border, soft fade) shown in a time window over the board.
Missing files are skipped, so the script runs with whatever assets exist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
A = HERE / "assets"

# (path, start_s, end_s, width_px, x, y)  x/y = top-left on the 1920x1080 canvas
INSERTS: list[tuple[Path, float, float, int, int, int]] = [
    # hook: real camera hardware (Mixkit free licence) in the board's empty areas
    (A / "hardware/hw01_ptz_dome_camera.mp4", 1.2, 4.6, 1000, 460, 160),
    (A / "hardware/hw06_police_control_room.mp4", 7.8, 11.3, 560, 1320, 520),
    (A / "hardware/hw03_dome_camera_haze.mp4", 12.4, 16.4, 600, 1260, 470),
    # cloud: real AWS console in the empty right column while the architecture draws (200-212 s)
    (A / "awsconsole/01_ec2.png", 200.2, 202.6, 690, 1200, 200),
    (A / "awsconsole/02_cloudfront.png", 202.7, 205.0, 690, 1200, 200),
    (A / "awsconsole/03_cognito.png", 205.1, 207.4, 690, 1200, 200),
    (A / "awsconsole/04_bedrock.png", 207.5, 209.7, 690, 1200, 200),
    (A / "awsconsole/05_cloudwatch.png", 209.8, 212.0, 690, 1200, 200),
    # real CloudWatch widgets: big on the blank board, then small beside the throughput numbers
    (A / "awsreal/cw_cpu.png", 212.3, 215.6, 1240, 340, 150),
    (A / "awsreal/cw_fleet.png", 216.4, 222.8, 560, 1340, 450),
]
FADE = 0.35
BORDER = 10
CREAM = "0xFCFAF5"


def main() -> None:
    src = HERE / "build/video_nosound.mp4"
    out = HERE / "build/video_overlaid.mp4"
    items = [i for i in INSERTS if i[0].exists()]
    for p, *_ in INSERTS:
        if not p.exists():
            print(f"skip (missing): {p.relative_to(HERE)}", file=sys.stderr)
    if not items:
        subprocess.run(["cp", str(src), str(out)], check=True)
        return
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    chains, last = [], "0:v"
    for n, (p, t0, t1, w, x, y) in enumerate(items, start=1):
        dur = t1 - t0
        if p.suffix == ".mp4":
            cmd += ["-i", str(p)]
        else:
            cmd += ["-loop", "1", "-framerate", "60", "-t", f"{dur:.3f}", "-i", str(p)]
        chains.append(
            f"[{n}:v]trim=duration={dur:.3f},setpts=PTS-STARTPTS,fps=60,scale={w}:-2,"
            f"pad=iw+{2 * BORDER}:ih+{2 * BORDER}:{BORDER}:{BORDER}:color={CREAM},format=yuva420p,"
            f"fade=t=in:st=0:d={FADE}:alpha=1,fade=t=out:st={dur - FADE:.3f}:d={FADE}:alpha=1,"
            f"setpts=PTS+{t0:.3f}/TB[o{n}]"
        )
        chains.append(f"[{last}][o{n}]overlay={x}:{y}:eof_action=pass:enable='between(t,{t0},{t1})'[v{n}]")
        last = f"v{n}"
    cmd += ["-filter_complex", ";".join(chains), "-map", f"[{last}]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", str(out)]
    subprocess.run(cmd, check=True)
    print(f"{len(items)} inserts -> {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
