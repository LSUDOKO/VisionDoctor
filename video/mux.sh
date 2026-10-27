#!/usr/bin/env bash
# Final mix: concat rendered parts, add narration + a synthesized music bed (ducked under the voice),
# burn line-by-line subtitles in brand colours → build/VisionDoctor_demo.mp4
set -euo pipefail
cd "$(dirname "$0")"
TOTAL=$(python3 -c "import json;print(json.load(open('timeline.json'))['total'])")
# 1) music bed: synthesized lo-fi track (98 BPM, Am-F-C-G) -> build/bgm.wav, exactly TOTAL seconds
../.venv/bin/python make_bgm.py
# 2) mix: music at -12 dB, sidechain-ducked ~6-8 dB under the voice (never to silence), normalise loudness
ffmpeg -y -v error -i build/narration.wav -i build/bgm.wav -filter_complex \
  "[1:a]volume=-12dB[bgm];[bgm][0:a]sidechaincompress=threshold=0.03:ratio=4:attack=30:release=600:makeup=1[duck];[0:a][duck]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map "[a]" -ar 48000 build/mix.wav
# 3) concat the rendered parts
ls build/part*.mp4 | sort | sed "s|^|file '$(pwd)/|;s|$|'|" > build/parts.txt
ffmpeg -y -v error -f concat -safe 0 -i build/parts.txt -c copy build/video_nosound.mp4
# (overlay steps go here, between concat and the final mux)
# 4) mux + burn subtitles (cream text on a dark box)
ffmpeg -y -v error -i build/video_nosound.mp4 -i build/mix.wav -map 0:v -map 1:a \
  -vf "subtitles=build/subs.srt:force_style='FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00F5FAFC,BackColour=&HB0081008,OutlineColour=&HB0081008,BorderStyle=4,Outline=6,Shadow=0,MarginV=24,Alignment=2'" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -shortest build/VisionDoctor_demo.mp4
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact build/VisionDoctor_demo.mp4
