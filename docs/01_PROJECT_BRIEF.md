# 01 — Project Brief

## 1. One-line pitch
**VisionDoctor is the AI that watches the cameras, so every other camera AI can be trusted.**
It detects camera faults with OpenCV 5, predicts how much accuracy the downstream AI has lost
(without labels), repairs what software can fix, verifies the repair, and dispatches a human
with evidence for what it can't.

## 2. Problem (with evidence)
Every vision system assumes its camera is fine. In practice cameras drift, defocus, fog up,
get dirty, get blocked, and freeze — and the AI on top silently degrades.

**Cities lose a large share of their cameras without knowing it** (public audits):
- Philadelphia (City Controller follow-up audit): only **32%** of sampled police cameras were
  functioning properly; problems included blurry, pixelated images and condensation in camera
  domes that made plates and suspects unreadable. Source: controller.phila.gov/?p=345;
  securitysystemsnews.com (see docs/09).
- Baltimore (Office of Legislative Audits, CitiWatch): **12% of 830** city-managed cameras
  not functional; the program **did not track camera uptime** nor have procedures to ensure
  timely repair. Source: WMAR-2 News.
- Pittsburgh (KDKA investigation): **45 of 163 (28%)** cameras not fully operational; a camera
  failed to capture a shooting of a 17-year-old. Source: CBS/KDKA.

**Camera faults break AI** (research):
- Michaelis et al., "Benchmarking Robustness in Object Detection" (615+ citations): standard
  detectors drop to **30–60%** of clean performance on corrupted images.
- Liu et al., IJCV 2024 (COCO-C / BDD100K-C): high-mAP detectors are still vulnerable to real
  camera-sensor corruptions; existing robustness fixes help only a little.

**Prior work stops short.** Tamper detection (Saglam 2009; Huang 2014; Sidnev 2018) raises
alarms only. A 2026 self-healing camera network (Attarha et al.) fixes rotation and redistributes
cameras with fixed rules for a few faults. Wischow et al. (2021) tie blur/noise to detection
capability but build no agent. **Nobody combines diagnosis + label-free AI-impact prediction +
verified self-repair + risk-ranked human escalation at fleet scale.**

## 3. Users and beneficiaries
| User | Need | What VisionDoctor gives them |
|---|---|---|
| City / campus security operations | Know which cameras actually work | Live fleet health + uptime tracking that audits found missing |
| Traffic & smart-city teams | ANPR / counting accuracy | Predicted accuracy per camera; auto-realign after drift |
| Factory quality / safety teams | Inspection cameras must stay calibrated | Early drift/defocus warnings before defects slip through |
| Maintenance technicians | Fewer wasted trips | Ticket with fault type, VLM description, evidence crop, location |
| Public | Cameras that work when incidents happen | Higher real uptime |

## 4. Innovation (20%) — the four novel contributions
1. **Label-free AI-impact prediction.** From image-health features alone, predict the drop in a
   detector's accuracy ("Camera 14 person detection: ~0.81 → ~0.52"). Trained with a
   *self-supervised agreement target*: detections on a degraded frame vs. the camera's own clean
   reference window — no human labels needed in deployment (docs/03 §6).
2. **Verified self-repair.** Agent applies a bounded software repair (homography realignment,
   exposure, dehaze, white balance, denoise), then **re-scans and re-predicts impact**; a repair
   only counts if metrics recover, otherwise it escalates.
3. **VLM root-cause description** using OpenCV 5's native VLM engine ("spider web across upper
   left"), so the technician brings the right tool.
4. **Risk-ranked repair queue.** Incidents are prioritized by *predicted AI harm × camera
   criticality*, not by alarm time.

## 5. Real-world impact (20%) — what we will prove
- **Time to detect**: minutes vs. weeks/months (audits found no uptime tracking).
- **Accuracy recovered**: % of lost detector mAP restored by verified repairs (measured, docs/06).
- **False alarms per camera-day** on clean footage (operators ignore noisy alarms — Saglam 2009).
- **Truck rolls avoided**: share of incidents fixed in software.
- **Cost**: $ per camera per month on COOL/Graviton (measured, docs/05 §6).

## 6. Judging-criteria map
| Criterion | Weight | How VisionDoctor scores |
|---|---|---|
| Technical execution (OpenCV 5 depth) | 30% | 11 checks across features module (ALIKED/LightGlue or ORB), USAC homography, LK optical flow, FFT, MOG2, dark-channel, Lab stats; repairs with `warpPerspective`, CLAHE, NL-means; new DNN engine detector; YuNet; native VLM |
| Innovation | 20% | §4 above |
| Real-world impact | 20% | §2 evidence + §5 measured outcomes |
| User experience | 10% | Fleet grid, incident queue with one-click approve, before/after slider, trace viewer, accessible status (icon + text, not color only) |
| Documentation & presentation | 10% | REPORT.md, diagrams, 5-min video (docs/08) |
| Cloud delivery, reproducibility, responsible ops | 10% | CDK IaC, pinned deps, local mode, CloudWatch dashboards, Cognito, least-privilege IAM, privacy (no face recognition, face blur, retention) |

**Special awards:** Agentic Vision (OpenCV output changes later tool calls; traces prove it) and
Best Use of COOL (core workload on Graviton with COOL; reproducible baseline comparison).

## 7. Scope boundaries (state these honestly in the report)
- Tamper/fault *detection* is prior art; our novelty is §4.
- Physical faults (defocus, dirty lens, hardware failure) cannot be fixed in software — we
  detect, explain and dispatch.
- Digital realignment crops the field of view; real PTZ re-homing is simulated via an
  ONVIF-style command stub (no real PTZ hardware in the demo).
