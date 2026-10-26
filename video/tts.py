"""Voice each narration line (edge-tts en-US-AriaNeural), measure real durations, and build
timeline.json, build/narration.wav and build/subs.srt."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
B = HERE / "build"
VOICE = "en-US-AriaNeural"
GAP, LEAD, SCENE_GAP, TAIL = 0.4, 1.0, 0.6, 3.0


def dur(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    lines = json.loads((HERE / "script.json").read_text())
    (B / "vo").mkdir(parents=True, exist_ok=True)
    t, prev, timeline = LEAD, None, []
    for ln in lines:
        mp3 = B / "vo" / f"{ln['id']}.mp3"
        txt = B / "vo" / f"{ln['id']}.txt"
        if not mp3.exists() or not txt.exists() or txt.read_text() != ln["text"]:
            subprocess.run([str(HERE / ".venv/bin/edge-tts"), "--voice", VOICE, "--rate", "+6%", "--text", ln["text"],
                            "--write-media", str(mp3)], check=True)
            txt.write_text(ln["text"])
        if prev and ln["scene"] != prev:
            t += SCENE_GAP
        d = dur(mp3)
        timeline.append({**ln, "start": round(t, 3), "end": round(t + d, 3)})
        t += d + GAP
        prev = ln["scene"]
    total = round(t + TAIL, 3)
    (HERE / "timeline.json").write_text(json.dumps({"total": total, "lines": timeline}, indent=1))
    inputs, filt = [], []
    for i, ln in enumerate(timeline):
        inputs += ["-i", str(B / "vo" / f"{ln['id']}.mp3")]
        ms = int(ln["start"] * 1000)
        filt.append(f"[{i}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(timeline))) +
                f"amix=inputs={len(timeline)}:normalize=0,apad=whole_dur={total}[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[out]",
                    "-ac", "2", "-ar", "48000", str(B / "narration.wav")], check=True)
    (B / "subs.srt").write_text("\n".join(
        f"{i}\n{srt_time(ln['start'])} --> {srt_time(ln['end'] + 0.15)}\n{ln['text']}\n" for i, ln in enumerate(timeline, 1)))
    print(f"{len(timeline)} lines, total {total:.1f}s")
    for ln in timeline:
        print(f"{ln['start']:7.2f} {ln['end'] - ln['start']:5.2f}  {ln['id']}")


if __name__ == "__main__":
    main()
