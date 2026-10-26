# 03 — OpenCV 5 Health Engine (Technical Execution, 30%)

This is the core of the score. Each check is small, explainable, and measurable. All code is
Python 3.12 with `import cv2` (OpenCV ≥ 5). Snippets are skeletons: Claude Code must complete,
type, test and **VERIFY** flagged APIs.

---

## 1. OpenCV 5 facts this design relies on
- Python names are unchanged (`cv2.<func>()`) even though C++ modules moved
  (`features2d → features`, `calib3d → geometry/calib/stereo/ptcloud`).
- `cv2.findHomography` uses the **USAC** framework; pass `cv2.USAC_MAGSAC` explicitly.
- `warpPerspective` / `remap` were rewritten in 5.0 (faster, more accurate) — our realign repair
  and the COOL benchmark both exercise them.
- `findContours` uses the new **TRUCO** algorithm automatically.
- DNN: new graph engine; `cv2.dnn.readNetFromONNX(path, engine=...)`. Documented constants include
  `cv2.dnn.ENGINE_CLASSIC` and `cv2.dnn.ENGINE_ORT`; **VERIFY** the constant name for the new
  engine (default `ENGINE_AUTO` tries the new engine first). Env override `OPENCV_FORCE_DNN_ENGINE`
  (1 classic, 2 new, 3 auto, 4 ORT). Log which engine actually loaded each model.
- Features module adds **ALIKED, DISK, LightGlue** and Annoy ANN search; SIFT/ORB/FAST/GFTT/MSER stay.
  **VERIFY** the Python class names and required model files for ALIKED/LightGlue; ORB/SIFT are the fallback.
- `ml` module moved to contrib → use scikit-learn for the impact regressor.
- New types such as `CV_Bool` masks exist; use uint8 masks unless a function documents `CV_Bool`.

---

## 2. Reference learning (`health/reference.py`)
Every camera learns what "healthy" looks like.

1. **Calibration window**: first `N=60` frames sampled over ≥ 10 min of known-good operation
   (simulator: clean segment; production: operator confirms).
2. **Two references per camera, by luminance bucket**: `day` and `night` (split on median V of
   HSV). Prevents night scenes from triggering exposure/haze alarms.
3. Stored per reference:
   - `background`: per-pixel median of downscaled frames (`np.median` over a stack, 960 px wide).
   - `keypoints/descriptors` on the background, masked to static regions (pixels whose temporal std
     is low) — moving objects never become anchors.
   - Per-tile (8×8 grid) baselines, mean and std over the window: Laplacian variance, Canny edge
     density, mean luminance, RMS contrast, dark-channel mean, Lab a/b means, noise sigma.
   - `activity_level`: mean absdiff between consecutive frames (for freeze detection).
   - Detector baseline: mean count and mean top-5 confidence of detections (used as runtime
     impact features, §6.4).
4. **Slow update**: only while overall health ≥ 0.9 for 24 h, EMA α=0.02, versioned
   (`reference_version`), so a slowly drifting camera cannot "teach" itself that drift is normal.

**Severity mapping (shared):** for metric `m` with reference mean μ and std σ, `z=(m-μ)/σ`
(signed per check direction); severity = 0 (z<2), 1 (2–3), 2 (3–4), 3 (4–6), 4 (6–9), 5 (≥9).
Score = `1 - severity/5`. Thresholds calibrated per §9.

---

## 3. The 11 health checks (`health/checks/*.py`)
Each returns `CheckResult(name, score, severity, evidence: dict, region_mask: np.ndarray | None)`.

### 3.1 Sharpness / defocus — `sharpness.py`
- Gray → `cv2.Laplacian(gray, cv2.CV_64F).var()`; Tenengrad: `cv2.Sobel` x/y, mean of gx²+gy².
- FFT high-frequency energy ratio: `np.fft.fft2` (or `cv2.dft`) on a 512×512 center crop;
  energy outside radius r=0.15·N divided by total.
- Global ratios vs. reference → defocus when **all tiles** drop together (smudge is local, §3.8).
- Evidence: `{lap_var, lap_ratio, tenengrad_ratio, hf_ratio}`.

### 3.2 Drift / displacement — `drift.py`
```python
orb = cv2.ORB_create(nfeatures=3000)            # fallback; prefer ALIKED+LightGlue (VERIFY API)
kp, des = orb.detectAndCompute(gray, mask=None)
matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
knn = matcher.knnMatch(ref_des, des, k=2)
good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
src = np.float32([ref_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
dst = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
H, inl = cv2.findHomography(src, dst, cv2.USAC_MAGSAC, 3.0)
corners = np.float32([[0,0],[w,0],[w,h],[0,h]]).reshape(-1,1,2)
disp = np.linalg.norm(cv2.perspectiveTransform(corners, H) - corners, axis=2).mean()
rot_deg = np.degrees(np.arctan2(H[1,0], H[0,0]))
```
- Evidence: `{inliers, inlier_ratio, mean_corner_disp_px, rot_deg, tx, ty, H}`.
- Low inlier ratio with low match count → not drift but **scene change / occlusion** (hand to §3.7).
- Matching runs on the **background model of the last K frames** (median of 5) to suppress people/cars.

### 3.3 Vibration / shake — `vibration.py`
- Burst of 15 frames. `cv2.goodFeaturesToTrack` on static mask → `cv2.calcOpticalFlowPyrLK`
  frame-to-frame → `cv2.estimateAffinePartial2D(..., method=cv2.RANSAC)` per pair.
- Std of per-frame translation (px) and rotation; vibration if std high but mean ≈ 0 (vs. drift = constant offset).

### 3.4 Haze / fog / condensation — `haze.py`
- Dark channel: `dc = cv2.erode(np.min(img, axis=2), cv2.getStructuringElement(cv2.MORPH_RECT,(15,15)))`;
  mean dark channel ↑, RMS contrast ↓, HSV saturation ↓ — all vs. reference (same luminance bucket).
- Condensation inside dome tends to be **non-uniform** → report tile map.

### 3.5 Glare / lens flare — `glare.py`
- HSV mask `V ≥ 250 & S ≤ 40`, `cv2.morphologyEx(OPEN)`, `cv2.connectedComponentsWithStats`.
- Fraction of saturated area and largest blob area vs. reference; time-of-day aware.

### 3.6 Exposure — `exposure.py`
- `cv2.calcHist` on gray: clip fractions (`≤5`, `≥250`), mean and median luminance vs. reference.
- Distinguish **under/over-exposure** from "lights off" (whole-scene drop at night is normal).

### 3.7 Occlusion / covered lens / foreign object — `occlusion.py`
- Per tile: Canny edge density (`cv2.Canny(gray, 50, 150)`) ratio vs. reference; entropy of the tile histogram.
- `cv2.createBackgroundSubtractorMOG2(history=500, detectShadows=False)` → foreground that stays
  static for > T seconds = foreign object.
- Occluded region = tiles with edge ratio < 0.2 AND (static foreground OR near-uniform intensity).
  `cv2.findContours` (TRUCO) on the tile mask → bounding boxes → evidence crops for the VLM.

### 3.8 Smudge / dirty lens / spider web — `smudge.py`
- Tile-wise Laplacian-variance ratio map vs. reference. Smudge = **local** partial loss
  (ratio 0.2–0.7) that **persists across ≥ 3 scans with different scene content** (edges reduced,
  not removed — unlike occlusion). Night + IR: thin bright high-frequency structures near the lens
  (spider web) → flag for VLM description.

### 3.9 Color cast / IR-cut failure — `color_cast.py`
- `lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)`; mean a, b (minus 128) vs. reference; gray-world
  deviation of BGR means. Daytime pink/magenta cast suggests a stuck IR-cut filter.

### 3.10 Noise — `noise.py`
- Immerkaer estimator: `cv2.filter2D(gray.astype(np.float32), -1, K)` with
  `K=[[1,-2,1],[-2,4,-2],[1,-2,1]]`; `σ = sqrt(π/2)·Σ|conv| / (6(W−2)(H−2))`. Compare to reference.

### 3.11 Freeze / dead stream — `freeze.py`
- Consecutive frames: mean `cv2.absdiff` < 0.5 AND identical md5 of a 64×36 grayscale thumbnail for
  > 20 s while reference `activity_level` says the scene normally moves. Also flags all-black/all-uniform frames.

### 3.12 `scan.py` and heat map
- Runs checks (cheap ones first; drift/vibration only every k-th scan unless triggered), combines into
  `overall_score = min over critical checks, weighted mean otherwise`, builds the 8×8 tile heat map
  (`heatmap.py`, rendered with `cv2.applyColorMap(..., cv2.COLORMAP_VIRIDIS)` for evidence images).
- Every check is timed; per-op timings feed the COOL benchmark (docs/05 §6).

---

## 4. Repairs (`repair/*.py`) — bounded, reversible, verified
Repairs produce a per-camera **correction profile** applied to the stream *before* the downstream
AI (the physical camera is untouched, except the simulated PTZ re-home stub).

| Repair | Trigger | OpenCV implementation | Bounds (guard enforces) |
|---|---|---|---|
| `realign` | drift | `cv2.warpPerspective(frame, np.linalg.inv(H), (w,h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)`; optional PTZ preset stub | rot ≤ 10°, corner disp ≤ 12% of diagonal, inlier ratio ≥ 0.5 |
| `exposure_fix` | exposure | CLAHE on Lab L: `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` + gamma LUT via `cv2.LUT` | gamma 0.5–2.0 |
| `dehaze` | haze | Dark-channel prior (He et al. 2009): atmospheric light from top 0.1% dark-channel pixels, transmission `t=1−ω·dc(I/A)`, refine with a guided filter implemented via `cv2.boxFilter` (ximgproc is contrib), `J=(I−A)/max(t,0.1)+A` | ω ≤ 0.95 |
| `white_balance` | color cast | Gray-world gains with `cv2.mean` + `cv2.multiply` (xphoto is contrib) | gains 0.5–2.0 |
| `denoise` | noise | `cv2.fastNlMeansDenoisingColored(img, None, h, h, 7, 21)` | h ≤ 15 |

**Verify** (`verify_repair`): apply profile to the next 5 frames → re-run the triggering check(s) +
impact predictor. Success iff the check severity drops ≤ 1 **and** predicted accuracy recovers by
≥ 50% of the predicted loss. Otherwise roll back and escalate. Defocus, smudge, occlusion, freeze
and hardware failure are **never** auto-repaired.

---

## 5. Night/day and false-alarm control
- Luminance-bucketed references (§2), hysteresis (fault must persist 2 consecutive scans before an
  incident opens, except freeze/occlusion > 80%), and per-check cooldowns.
- Weather vs. hardware: haze across **all** cameras at one site at once → "site weather" note,
  lower priority; haze on one camera only → condensation, dispatch.

---

## 6. AI-impact predictor (`impact/`) — the key innovation

### 6.1 Detector (OpenCV 5 DNN, new engine)
- Use a permissively licensed ONNX detector from the OpenCV model zoo on Hugging Face
  (`huggingface.co/opencv` — e.g. YOLOX or NanoDet; **VERIFY** exact repo names and input
  size/pre-/post-processing from the model card). Avoid AGPL models (e.g. Ultralytics YOLOv8)
  unless the repo license is compatible.
- `net = cv2.dnn.readNetFromONNX(path)` (engine auto); `blob = cv2.dnn.blobFromImage(...)`;
  `net.setInput(blob)`; `out = net.forward()`; NMS with `cv2.dnn.NMSBoxes`.
- Classes of interest: person, car, bus, truck, bicycle, motorcycle.

### 6.2 Why label-free
In deployment nobody labels camera frames. We train the predictor **in simulation**, where for every
degraded frame we also have the identical clean frame, so the clean frame's detections act as
pseudo-ground-truth. No human annotation is needed — and we validate against real human labels (MOT17).

### 6.3 Target
`agreement = F1@IoU0.5(dets(degraded_frame), dets(clean_frame))` per class group, conf ≥ 0.4.
Predicted accuracy drop = `1 − agreement`.

### 6.4 Features (all computable at runtime without labels)
All 11 check scores and raw evidence ratios (sharpness ratios, inlier ratio, corner displacement,
dark-channel delta, contrast ratio, glare fraction, clip fractions, occluded fraction, Lab deltas,
noise σ ratio) **plus** detector self-signals: detection count ratio vs. baseline for that hour,
mean top-5 confidence ratio, confidence entropy.

### 6.5 Model and training
- `sklearn.ensemble.HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05)`; 5-fold
  **grouped** CV by video sequence (never leak frames of one sequence across folds).
- Training grid: 11 fault types × 5 severities × combinations of 2 (sampled) × ≥ 3,000 frames.
- Export with `skops` or joblib; version it with the reference version.
- Per-camera calibration offset: after a camera's reference window, fit a 1-parameter offset so
  predicted agreement on clean frames ≈ 1.0.

### 6.6 Validation (docs/06): Spearman ρ and MAE vs. (a) agreement target on held-out sequences,
(b) **true** mAP drop on MOT17 ground truth, (c) qualitative on CDnet real `badWeather`/`cameraJitter`.

---

## 7. Privacy: face blur on evidence (`privacy/face_blur.py`)
- YuNet face detector from the OpenCV zoo (`huggingface.co/opencv`, face_detection_yunet ONNX — **VERIFY** repo name).
- `det = cv2.FaceDetectorYN.create(model_path, "", (w, h), 0.6, 0.3, 5000)`; `det.setInputSize((w,h))`;
  `_, faces = det.detect(img)` → `cv2.GaussianBlur` each box (padded 20%) before any evidence image
  is stored or shown. No identification, no embeddings, no face recognition anywhere.

---

## 8. VLM fault description (`vlm/describe.py`) — OpenCV 5 native VLM
- Base on `samples/dnn/vlm_inference.py` from the OpenCV 5.x repo: PaliGemma2-3B-pt-224
  (`huggingface.co/google/paligemma2-3b-pt-224`, ONNX export `huggingface.co/nklskyoy/paligemma2-3b-pt-224-onnx`).
  The sample takes `--siglip`, `--embedding`, `--gemma`, `--tokenizer_path`, `--input`, `--prompt`,
  `--max_new_tokens`; uses `cv.dnn.Tokenizer.load(...)`, `tokenizer.encode/decode`,
  `cv.dnn.readNetFromONNX`, `setInput`, `forward`. Default prompt `"cap en\n"`.
- Use: crop the fault region (from `region_mask`), face-blur it, caption with `"cap en\n"`; optionally
  try a question prompt (e.g. `"answer en what is blocking the view?\n"`) — **VERIFY** what the
  pretrained (pt) checkpoint answers well; keep whichever is more reliable in tests.
- Gemma license must be accepted on Hugging Face before download (document in README).
- Resource: a 3B model needs ~12+ GB RAM in FP32 → run VLM only on escalations, on an `m8g` instance
  (not on small c8g workers), with a 60 s timeout and an LRU cache by region hash. If unavailable,
  the incident still proceeds with the rule-based fault description.

---

## 9. Threshold calibration (document in REPORT.md)
1. Run all checks on clean footage (CDnet `baseline` category + clean MOT17 segments + the clean
   segments of each simulated camera).
2. Set each check's alarm threshold at the **99.5th percentile** of its clean-score distribution
   (target ≤ 1 false incident per camera-day at 1 scan/min after 2-scan hysteresis).
3. Validate recall per fault type and severity on injected faults (docs/06). Report the curves.
4. Freeze thresholds in `config.py` with a comment pointing to `results/calibration/*.json`.
