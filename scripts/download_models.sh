#!/usr/bin/env bash
# ONNX models from the OpenCV model zoo on Hugging Face (Apache-2.0 / MIT).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p models
B=https://huggingface.co/opencv
fetch() { [ -s "$2" ] || curl -fsSL --retry 3 -o "$2" "$1"; }
fetch $B/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx models/yolox.onnx
fetch $B/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx models/yunet.onnx
# PaliGemma2 VLM (optional, ~12 GB RAM; Gemma license must be accepted on HF first)
if [ "${VD_VLM:-0}" = "1" ]; then
  R=https://huggingface.co/nklskyoy/paligemma2-3b-pt-224-onnx/resolve/main
  mkdir -p models/paligemma2
  for f in siglip.onnx embedding.onnx gemma.onnx tokenizer.json; do fetch "$R/$f" "models/paligemma2/$f" || echo "missing $f (check repo file names)"; done
fi
sha256sum models/*.onnx
curl -fsSL -o models/face_sample.jpg $B/face_detection_yunet/resolve/main/example_outputs/largest_selfie.jpg || true
# Trained impact predictor (produced by `make eval-impact`, frozen in results/final/).
[ -s models/impact_hgb.joblib ] || cp results/final/impact_hgb.joblib models/impact_hgb.joblib
