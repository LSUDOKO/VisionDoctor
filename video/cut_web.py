"""Cut the live-site recording into the three narrated phases and export 30 fps frames."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
m = json.loads((HERE / "build/web/marks.json").read_text())
M, V = m["marks"], m["video"]
segs = [(M["fleet"] - 0.3, 4.6), (M["camera"] - 1.4, 8.3), (M["incidents"] + 0.8, 2.8), (M["trace"] + 0.6, 2.9)]
out = HERE / "assets/web"
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
parts = []
for i, (s, d) in enumerate(segs):
    p = HERE / f"build/web/seg{i}.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{s:.2f}", "-i", V, "-t", f"{d:.2f}", "-vf", "fps=30,scale=1600:900",
                    "-an", "-c:v", "libx264", "-crf", "16", str(p)], check=True)
    parts.append(p)
lst = HERE / "build/web/list.txt"
lst.write_text("".join(f"file '{p}'\n" for p in parts))
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-q:v", "3",
                "-start_number", "0", str(out / "f%04d.jpg")], check=True)
n = len(list(out.glob("f*.jpg")))
(out / "count.json").write_text(json.dumps({"n": n}))
print(n, "frames")
