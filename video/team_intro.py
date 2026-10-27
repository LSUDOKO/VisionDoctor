"""Replace the narrated intro (31.0-46.0 s) with the builder's own on-camera intro, voice included.

Inputs: build/video_overlaid.mp4, build/narration.wav, build/subs.srt, assets/team.mp4.
Output: build/VisionDoctor_demo.mp4 (music bed regenerated for the new length, subtitles re-timed).
Run after mux.sh.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
B = HERE / "build"
CUT_IN, CUT_OUT = 31.0, 46.0  # silence before "This is VisionDoctor" / before "Step one: scan"
TEAM_LEN = 17.3  # the clip's speech ends at ~17.0 s
SHIFT = TEAM_LEN - (CUT_OUT - CUT_IN)
TEAM_SUBS = [
    (0.0, 8.2, "Hi, I am Arpit. I built VisionDoctor, an AI that watches the city cameras,"),
    (8.2, 17.0, "finds when they break, fixes what software can fix, and calls a human for the rest. Built with OpenCV on AWS."),
]
SUB_STYLE = ("FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00F5FAFC,BackColour=&HB0081008,"
             "OutlineColour=&HB0081008,BorderStyle=4,Outline=6,Shadow=0,MarginV=24,Alignment=2")


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def font(spec: str) -> str:
    return subprocess.run(["fc-match", "-f", "%{file}", spec], capture_output=True, text=True, check=True).stdout


def ts(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def parse_ts(s: str) -> float:
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000


def team_clip() -> None:
    """Board background, big cream-framed camera shot, lower-third name card."""
    bold, mono = font("DejaVu Sans:bold"), font("DejaVu Sans Mono")
    (B / "n1.txt").write_text("Arpit")
    (B / "n2.txt").write_text(" builder of VisionDoctor ")
    (B / "n3.txt").write_text("OpenCV AI Competition 2026")
    ff("-i", str(HERE / "assets/team.mp4"), "-f", "lavfi", "-i", f"color=c=0x0b0d0a:s=1920x1080:r=60:d={TEAM_LEN}",
       "-filter_complex",
       f"[0:v]trim=duration={TEAM_LEN},setpts=PTS-STARTPTS,fps=60,crop=820:461:17:0,scale=1440:810:flags=lanczos,"
       "eq=contrast=1.06:brightness=-0.035:saturation=1.08,curves=all='0/0 0.75/0.70 1/0.92',"
       "pad=1460:830:10:10:color=0xFCFAF5[cam];"
       "[1:v]drawgrid=w=60:h=60:t=1:color=0x151a12[bg];"
       "[bg][cam]overlay=230:50:shortest=1,"
       "drawbox=x=262:y=640:w=600:h=170:color=0x0b0d0a@0.82:t=fill,"
       f"drawtext=fontfile={bold}:textfile={B}/n1.txt:expansion=none:fontcolor=0xfcfaf5:fontsize=64:x=290:y=655,"
       "drawbox=x=290:y=735:w=500:h=48:color=0xffe95c:t=fill,"
       f"drawtext=fontfile={bold}:textfile={B}/n2.txt:expansion=none:fontcolor=0x1a3300:fontsize=32:x=296:y=742,"
       "fade=t=in:st=0:d=0.4,fade=t=out:st=16.9:d=0.4",
       "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(B / "team_clip.mp4"))
    # voice: rumble/noise clean-up, levelled, padded to the clip length
    ff("-i", str(HERE / "assets/team.mp4"), "-vn", "-af",
       f"atrim=0:{TEAM_LEN},highpass=f=80,afftdn=nf=-25,loudnorm=I=-18:TP=-1.5,"
       f"afade=t=out:st={TEAM_LEN - 0.3}:d=0.3,apad=whole_dur={TEAM_LEN}",
       "-ar", "48000", "-ac", "1", str(B / "team_voice.wav"))


def narration() -> float:
    ff("-i", str(B / "narration.wav"), "-i", str(B / "team_voice.wav"), "-filter_complex",
       f"[0:a]aformat=sample_rates=48000:channel_layouts=mono,asplit[n1][n2];"
       f"[n1]atrim=0:{CUT_IN},asetpts=PTS-STARTPTS[a];[n2]atrim={CUT_OUT},asetpts=PTS-STARTPTS[c];"
       f"[1:a]aformat=sample_rates=48000:channel_layouts=mono[b];[a][b][c]concat=n=3:v=0:a=1[o]",
       "-map", "[o]", str(B / "narration_team.wav"))
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(B / "narration_team.wav")], capture_output=True, text=True, check=True).stdout
    return float(out)


def music(total: float) -> None:
    subprocess.run([str(HERE.parent / ".venv/bin/python"), str(HERE / "make_bgm.py")], check=True,
                   env={**os.environ, "BGM_TOTAL": f"{total:.3f}"})
    ff("-i", str(B / "narration_team.wav"), "-i", str(B / "bgm.wav"), "-filter_complex",
       "[1:a]volume=-12dB[bgm];[bgm][0:a]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600:makeup=1[duck];"
       "[0:a][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[a]",
       "-map", "[a]", "-ar", "48000", str(B / "mix_team.wav"))


def subtitles() -> None:
    blocks = [b for b in (B / "subs.srt").read_text().strip().split("\n\n") if b.strip()]
    cues: list[tuple[float, float, str]] = []
    for blk in blocks:
        lines = blk.splitlines()
        a, b = (parse_ts(x.strip()) for x in lines[1].split("-->"))
        text = "\n".join(lines[2:])
        if b <= CUT_IN:
            cues.append((a, b, text))
        elif a >= CUT_OUT:
            cues.append((a + SHIFT, b + SHIFT, text))
    cues += [(CUT_IN + a, CUT_IN + b, t) for a, b, t in TEAM_SUBS]
    cues.sort()
    (B / "subs_team.srt").write_text("\n".join(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n" for i, (a, b, t) in enumerate(cues, 1)))


def final() -> None:
    v = str(B / "video_overlaid.mp4")
    ff("-i", v, "-i", str(B / "team_clip.mp4"), "-i", str(B / "mix_team.wav"), "-filter_complex",
       f"[0:v]split[v1][v2];[v1]trim=0:{CUT_IN},setpts=PTS-STARTPTS[a];[v2]trim={CUT_OUT},setpts=PTS-STARTPTS[c];"
       f"[1:v]setpts=PTS-STARTPTS[b];[a][b][c]concat=n=3:v=1:a=0,"
       f"subtitles={B}/subs_team.srt:force_style='{SUB_STYLE}'[v]",
       "-map", "[v]", "-map", "2:a", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(B / "VisionDoctor_demo.mp4"))


if __name__ == "__main__":
    team_clip()
    total = narration()
    music(total)
    subtitles()
    final()
    print(f"total {total:.2f} s -> build/VisionDoctor_demo.mp4")
