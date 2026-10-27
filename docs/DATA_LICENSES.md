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

## Stock footage (demo video)

Opening b-roll in the demo video. All clips from Mixkit under the [Mixkit Stock Video Free License](https://mixkit.co/license/#videoFree)
(free for commercial and personal use, no attribution required). Mixkit pages credit no individual author, so the author is listed as Mixkit (Envato).
Originals: 1280x720 previews, trimmed to 4.5 s, scaled/cropped to 1920x1080 at 30 fps, slightly desaturated. Files live in `video/assets/hardware/` (not committed).

| File | Shows | Source | Author | License |
|---|---|---|---|---|
| hw01_ptz_dome_camera.mp4 | Wall-mounted PTZ dome camera rotating | https://mixkit.co/free-stock-video/security-camera-rotates-and-follow-the-object-48922/ | Mixkit (Envato) | Mixkit Free License |
| hw02_street_pole_cctv.mp4 | Street light pole with CCTV cameras | https://mixkit.co/free-stock-video/street-lights-with-cctv-26432/ | Mixkit (Envato) | Mixkit Free License |
| hw03_dome_camera_haze.mp4 | Dome camera in smoke/haze, server racks behind | https://mixkit.co/free-stock-video/close-up-of-security-camera-and-smoke-23280/ | Mixkit (Envato) | Mixkit Free License |
| hw04_technician_installing_camera.mp4 | Technician installing a camera in a data center | https://mixkit.co/free-stock-video/installing-a-security-camera-in-data-center-22972/ | Mixkit (Envato) | Mixkit Free License |
| hw05_control_room_video_wall.mp4 | Operators in front of a CCTV video wall | https://mixkit.co/free-stock-video/security-camera-crew-working-in-control-center-23268/ | Mixkit (Envato) | Mixkit Free License |
| hw06_police_control_room.mp4 | Police/security control room with camera wall | https://mixkit.co/free-stock-video/police-control-room-receive-an-alarm-23103/ | Mixkit (Envato) | Mixkit Free License |
| hw07_operators_cctv_monitors.mp4 | Operators watching multi-camera monitors | https://mixkit.co/free-stock-video/surveillance-team-looking-at-monitors-23016/ | Mixkit (Envato) | Mixkit Free License |
