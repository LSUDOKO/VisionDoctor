#!/usr/bin/env bash
# Downloads small, static-camera evaluation footage into data/.
# Full CDnet 2014 (~11 GB) and MOT17 frames (5.9 GB) are too large for a laptop run;
# we use MOT17 sequence videos + MOT17 labels and the OpenCV vtest.avi sample.
# See docs/DEVIATIONS.md and docs/DATA_LICENSES.md.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/videos data/mot17
fetch() { [ -s "$2" ] || curl -fsSL --retry 3 -o "$2" "$1"; }
fetch https://raw.githubusercontent.com/opencv/opencv/4.x/samples/data/vtest.avi data/videos/vtest.avi
for s in 02 04 09; do
  fetch "https://motchallenge.net/sequenceVideos/MOT17-$s-SDP-raw.webm" "data/videos/MOT17-$s.webm"
done
fetch https://motchallenge.net/data/MOT17Labels.zip data/mot17/MOT17Labels.zip
if [ ! -d data/mot17/train ]; then
  (cd data/mot17 && unzip -q -o MOT17Labels.zip 'train/MOT17-0[249]-SDP/*')
fi
# Optional: CDnet 2014 (set VD_CDNET=1; server is often offline)
if [ "${VD_CDNET:-0}" = "1" ]; then
  fetch http://jacarini.dinf.usherbrooke.ca/static/dataset/dataset2014.zip data/cdnet2014.zip || echo "CDnet unavailable"
fi
sha256sum data/videos/* > data/SHA256SUMS
echo "data ready"
