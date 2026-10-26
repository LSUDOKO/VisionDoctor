# Data and model licenses

Datasets are downloaded by `scripts/download_data.sh` and never redistributed in this repo.

| Asset | Source | License / terms | Use |
|---|---|---|---|
| MOT17 sequence videos (MOT17-02/04/09 SDP) and labels | motchallenge.net (Milan et al., 2016) | CC BY-NC-SA 3.0 | Static-camera footage; real person labels for true AP validation (E3b, E4) |
| `vtest.avi` | OpenCV samples (github.com/opencv/opencv, samples/data) | Apache-2.0 (OpenCV repo) | Static pedestrian camera |
| CDnet 2014 | changedetection.net (Wang et al., 2014) | research use | Optional (`VD_CDNET=1`); server was unreachable during the build |
| YOLOX-S ONNX | huggingface.co/opencv/object_detection_yolox | Apache-2.0 | Downstream detector for impact prediction |
| YuNet ONNX | huggingface.co/opencv/face_detection_yunet | MIT | Face blurring on evidence images |
| PaliGemma2-3B (optional) | huggingface.co/google/paligemma2-3b-pt-224, ONNX: nklskyoy/paligemma2-3b-pt-224-onnx | Gemma Terms of Use — accept on Hugging Face first | VLM fault captions |

Cite: Milan et al., "MOT16: A Benchmark for Multi-Object Tracking", 2016; Wang et al., "CDnet 2014", CVPRW 2014;
Ge et al., "YOLOX", 2021; Wu et al., "YuNet", 2023.
