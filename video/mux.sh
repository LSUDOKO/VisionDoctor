#!/usr/bin/env bash
# Final mix: concat rendered parts, add narration + a quiet generated pad (ducked under the voice),
# burn line-by-line subtitles in brand colours → build/VisionDoctor_demo.mp4
set -euo pipefail
cd "$(dirname "$0")"
TOTAL=$(python3 -c "import json;print(json.load(open('timeline.json'))['total'])")
FADE_AT=$(python3 -c "print(${TOTAL}-4)")
# 1) ambient pad: slow Am–F–C–G progression from sine partials with a gentle swell, low-passed
ffmpeg -y -v error -f lavfi -i "aevalsrc=0.16*(0.55+0.45*sin(2*PI*t/8-PI/2))*(sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*1*t)+0.6*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*1.5*1*t)+0.45*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*2*1*t)+0.2*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*2.52*t))|0.16*(0.55+0.45*sin(2*PI*t/8-PI/2))*(sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*1.003*t)+0.6*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*1.5*1.003*t)+0.45*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*2*1.003*t)+0.2*sin(2*PI*if(eq(floor(mod(t\,32)/8)\,0)\,110\,if(eq(floor(mod(t\,32)/8)\,1)\,87.31\,if(eq(floor(mod(t\,32)/8)\,2)\,130.81\,98)))*2.52*t)):s=48000:d=${TOTAL}" \
  -af "lowpass=f=900,aecho=0.8:0.7:120:0.35,afade=t=in:d=3,afade=t=out:st=${FADE_AT}:d=4" build/pad.wav
# 2) duck the pad under the narration, mix, normalise loudness
ffmpeg -y -v error -i build/narration.wav -i build/pad.wav -filter_complex \
  "[1:a]volume=-16dB[pad];[pad][0:a]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[duck];[0:a][duck]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]" \
  -map "[a]" -ar 48000 build/mix.wav
# 3) concat the rendered parts
ls build/part*.mp4 | sort | sed "s|^|file '$(pwd)/|;s|$|'|" > build/parts.txt
ffmpeg -y -v error -f concat -safe 0 -i build/parts.txt -c copy build/video_nosound.mp4
# 4) mux + burn subtitles (cream text on a dark box)
ffmpeg -y -v error -i build/video_nosound.mp4 -i build/mix.wav -map 0:v -map 1:a \
  -vf "subtitles=build/subs.srt:force_style='FontName=DejaVu Sans,FontSize=15,PrimaryColour=&H00F5FAFC,BackColour=&HB0081008,OutlineColour=&HB0081008,BorderStyle=4,Outline=6,Shadow=0,MarginV=24,Alignment=2'" \
  -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -movflags +faststart -shortest build/VisionDoctor_demo.mp4
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate -of compact build/VisionDoctor_demo.mp4
