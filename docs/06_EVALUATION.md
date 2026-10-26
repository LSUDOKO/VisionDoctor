# 06 — Evaluation Plan (evidence for Technical, Impact and both Awards)

All experiments are scripts in `eval/`, seeded, writing JSON/CSV/PNG to `results/`. Report every
number with a 95% bootstrap confidence interval (1,000 resamples, grouped by sequence).

## 1. Datasets (download via `scripts/download_data.sh`)
| Dataset | Use | Notes |
|---|---|---|
| **CDnet 2014** (changedetection.net) | Static-camera footage; clean `baseline` for calibration; **real faults** in `cameraJitter`, `badWeather`, `nightVideos`, `PTZ`, `turbulence`, `lowFramerate` | research use; cite Wang et al. 2014 |
| **MOT17** (motchallenge.net) | Static sequences (e.g. MOT17-02, -04, -09 — **VERIFY** which are static) with person boxes → **true** mAP for validating the impact predictor | CC BY-NC-SA 3.0; cite Milan et al. |
| **imagecorruptions** (pip, bethgelab) | ImageNet-C/COCO-C corruption functions: `corrupt(img, corruption_name=..., severity=1..5)` (fog, defocus_blur, motion_blur, gaussian_noise, brightness, contrast, jpeg_compression, …) | from Michaelis et al. 2019 |
| Own injectors (`sim/faults.py`) | Faults not covered above | below |

Check licenses into `docs/DATA_LICENSES.md`. Never redistribute datasets in the repo.

## 2. Fault injection and fleet simulator
Own injectors (OpenCV): `drift` (`warpPerspective`, rot 0.5–15°, shift 1–15%), `vibration`
(per-frame random affine jitter), `occlusion` (opaque patch / tape / leaf texture, 5–100% area),
`smudge` (local blur blob + slight brightening, alpha-blended), `spider_web` (procedural thin bright
curves, night), `condensation` (non-uniform fog mask), `glare` (additive radial flare), `color_cast`
and `ir_cut_stuck` (channel gains / magenta tint), `exposure` (gain + gamma), `freeze` (repeat frame),
`dead` (black/uniform). Each takes `severity ∈ {1..5}` with documented parameters.

Scenario file (`sim/scenarios/demo.yaml`):
```yaml
seed: 7
cameras: 12
fps: 2
duration_s: 600
sources: [cdnet/baseline/highway, cdnet/baseline/office, mot17/MOT17-04, ...]
events:
  - {t: 60,  camera: cam-03, fault: drift,     severity: 4}
  - {t: 120, camera: cam-07, fault: haze,      severity: 3}
  - {t: 180, camera: cam-01, fault: smudge,    severity: 3}
  - {t: 240, camera: cam-10, fault: occlusion, severity: 5}
  - {t: 300, camera: cam-05, fault: freeze,    severity: 5}
  - {t: 360, camera: cam-08, fault: glare,     severity: 2, duration_s: 20}  # transient
```
Ground truth (`results/sim/<run>/truth.jsonl`) records fault onset/offset per camera.

## 3. Experiments
**E1 — Fault detection.** Per fault type × severity: precision, recall, F1, time-to-detect (s).
Baseline: a classic tamper detector (global edge/entropy/brightness thresholds without references or
hysteresis, after Saglam 2009 / Huang 2014). Figure: recall vs. severity curves.

**E2 — False alarms.** Long clean runs (≥ 2,000 scans per camera across day/night sources):
false incidents per camera-day at 1 scan/min. Target ≤ 1. Compare with/without luminance-bucketed
references and hysteresis (ablation).

**E3 — AI-impact prediction (headline innovation).**
(a) Held-out sequences: Spearman ρ and MAE between predicted and actual agreement-based drop.
(b) MOT17 with real labels: Spearman ρ between predicted drop and **true mAP@0.5 drop**
(compute AP with `pycocotools` or a verified implementation).
(c) Feature importance (permutation) → which health signals matter most.
Figure: predicted vs. true scatter with identity line.

**E4 — Repair effectiveness.** For drift/exposure/haze/color/noise at severities 1–5: verified-repair
success rate; **accuracy recovered** = (AP_after − AP_degraded)/(AP_clean − AP_degraded); residual
drift after realignment. Figure: before/after AP bars per fault.

**E5 — Agent quality.** On 100 generated incidents with a ground-truth correct action
(auto-fix / approval / watch / close-as-transient):
| Agent | Metrics |
|---|---|
| Alarm-only baseline (always alert operator) | operator alerts, missed faults |
| PolicyAgent | correct-outcome rate, unnecessary escalations, missed escalations, steps, latency |
| BedrockAgent | same + tokens and $ per incident; guard blocks; multi-fault cases |
Headline: **operator workload reduction** = alerts avoided vs. alarm-only baseline at equal or better recall.
Also report trace completeness (100% of decisions linked to an OpenCV tool output).

**E6 — COOL benchmark.** docs/05 §6.

**E7 — Real faults (qualitative + quantitative where labels allow).** Run on CDnet `cameraJitter`,
`badWeather`, `nightVideos`, `PTZ`: what the system flagged and why; PTZ legitimately moves —
report how often it's (wrongly) flagged as drift.

## 4. Failure cases to look for and report honestly
- Legitimate scene changes (construction, parked truck) look like drift/occlusion.
- Heavy rain/snow vs. smudge confusion; site-wide weather vs. condensation.
- PTZ/patrolling cameras (motion is intended) — needs a `ptz=true` camera flag.
- Night IR noise and headlight glare.
- Low-texture scenes (blank walls, sky) give few keypoints → drift check abstains (report abstention rate).
- Impact predictor trained on simulated faults may under-estimate real combined faults.
- VLM captions that are vague or wrong (show examples).

## 5. Outputs used by the report and video
`results/summary.md` auto-generated by `eval/summarize.py` with all tables; figures under
`results/figs/`. REPORT.md may only quote numbers from these files.
