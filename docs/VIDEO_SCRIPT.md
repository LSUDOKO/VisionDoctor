# VisionDoctor — 4½-minute demo video: script + storyboard

**Format:** 1920×1080, 60 fps, ≤ 5:00 (competition limit). **Voice:** edge-tts `en-US-AriaNeural`, subtitles line by line.
**Look (brand):** black board `#0b0f08`, cream marker ink `#fcfaf5`, yellow highlighter `#ffe95c` for the one key
word per line, pastel sticky notes (mint `#d5f5c2`, teal `#a8e5e5`, blush `#f6d0ff`), terracotta `#cb5521` only for
failures/blocks. Fonts: Bricolage Grotesque 800 (numbers, titles), Roboto Mono (labels). Hand-drawn: every shape is
"drawn" by a marker stroke before it is explained.
**One continuous diagram:** the whole video lives on one fixed board. The camera zooms into one part, explains it with
one concrete real example, then pulls back as that part locks in. Labels sit on the thing they name; ≤ 7 words on
screen at once. No bullet lists, no stock icons, no glows, no crossfades.

**Every claim is real.** Proof assets come from this repo: real MOT17 frames run through our code, our detector's
boxes, our screenshots, and numbers from `results/final/`. Problem facts come from the public audits cited in
`docs/09_REFERENCES.md`.

## The board (fixed layout, never reshuffles)

```
 ┌──────────────── TOP: AGENT ────────────────┐
 │  Bedrock brain → MCP toolbox → GUARD gate   │
 └─────────────────────┬───────────────────────┘
LEFT: CITY              CENTER: THE LOOP                         RIGHT: AWS CLOUD
camera grid   →   [1 SCAN] → [2 PREDICT] → [3 REPAIR+VERIFY] →   Graviton4 · Bedrock ·
(audits)                         ↘ [ESCALATE → human]             S3/DynamoDB · CloudFront → dashboard
                       BOTTOM: RESULTS BAND (big numbers)          FAR BOTTOM: WHO IT HELPS
```

## Script and timed storyboard

Times are estimates (~2.7 words/s); the build times each shot to the real length of its voice line.

### 0:00–0:32 · Hook: the problem (LEFT: city)

| # | ~Time | Narration | On screen (picture first, words second) | Proof |
|---|---|---|---|---|
| 1 | 0:01 | When a city camera stops working, who notices? | A marker draws one street camera on a pole; a big hand-drawn **?** appears beside it. | — |
| 2 | 0:05 | Audits found that in Philadelphia, only 32 percent of sampled police cameras were working properly. | Pull back: a grid of 10 cameras is drawn; only ~3 get a yellow "working" tick. Label: **"Philadelphia: 32% working"**. | Philadelphia City Controller audit |
| 3 | 0:12 | In Pittsburgh, 45 of 163 cameras were not fully operational. Baltimore did not even track camera uptime. | A second grid: a bar of 163 small marks, 45 crossed in terracotta. A blank clipboard labelled **"uptime: not tracked"**. | KDKA (Pittsburgh), WMAR-2 (Baltimore audit) |
| 4 | 0:20 | And the AI on those cameras fails silently with them. Detectors can fall to 30 to 60 percent of their clean performance on corrupted images. | A real foggy street frame; detection boxes fade out one by one. A bar shrinks from 100% to the 30–60% band. | Michaelis et al. 2019 |

### 0:32–0:46 · Intro (CENTER: loop skeleton)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 5 | 0:32 | This is VisionDoctor: the AI that watches the cameras, so every other camera AI can be trusted. | The yellow **vd** logo tile is drawn; the name is written beside it. | — |
| 6 | 0:39 | It runs one loop. Scan, diagnose, predict the damage, repair, verify, or call a human. | Five empty boxes are drawn left to right, linked by arrows that animate in the direction of flow, plus a branch down to a "human" stick figure. Each box gets a one-word label as it is spoken. | — |

### 0:46–1:30 · Step 1: Scan (zoom into box 1)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 7 | 0:46 | Step one: scan. Each camera first learns what healthy looks like, from its own clean footage. | Zoom in. A real MOT17-04 street frame appears; a stack of 60 thin frames collapses into one clean **reference**. | Real reference frame from our code |
| 8 | 0:53 | Then eleven OpenCV 5 checks compare every new burst of frames against that reference. | 11 short labels are drawn around the frame one by one (drift, haze, glare, smudge…). | `src/visiondoctor/health/checks/` |
| 9 | 1:00 | Here the camera has been knocked five degrees. ORB features and a USAC MAGSAC homography measure the drift exactly. | The real frame rotates 5°; yellow match lines connect keypoints between reference and current. Label: **"rotation 5.0°"** on the frame. | Real ORB + MAGSAC output on the injected 5° drift |
| 10 | 1:08 | Other checks catch haze, glare, smudges, occlusion, noise, colour casts, blur, shaking and frozen streams. | A 3×3 grid of real faulty frames is drawn tile by tile, each with its quality heat map and severity number. | Real injector + detector outputs |
| 11 | 1:16 | On real MOT17 street footage, VisionDoctor catches 91 percent of severe faults. A classic tamper detector catches 24. | Pull back. Two hand-drawn bars: **91%** in forest ink vs **24%** in grey. Box 1 locks in (ink fills). | `results/final/e1_detection.json` (0.911 vs 0.239) |

### 1:30–2:05 · Step 2: Predict impact without labels (zoom into box 2, the key innovation)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 12 | 1:30 | Step two is our key idea. How much accuracy has the AI on this camera lost, with no labels at all? | Zoom in; a highlighted question: **"accuracy lost? no labels"**. | — |
| 13 | 1:37 | In simulation, every degraded frame has an identical clean twin. How well the detector agrees with itself on the twin becomes the training target. | Two real frames side by side, clean and hazy, with our YOLOX boxes on both; matching boxes connect; a fraction becomes **"agreement 0.62"**. | Real detector boxes; `impact/agreement.py` |
| 14 | 1:47 | A gradient boosted model learns to predict that loss from the health signals alone. | The health signals (sharpness, drift, haze…) flow as arrows into a small tree diagram that outputs **"predicted accuracy"**. | `impact/predictor.py` |
| 15 | 1:53 | Checked against real human labels, its predictions rank the true accuracy drop with a correlation of 0.5. | Our real scatter plot (predicted vs true MOT17 AP drop) is drawn point by point; label **"ρ = 0.50"**. Box 2 locks in. | `results/final/e3_impact.json` (ρ 0.504) |

### 2:05–2:42 · Step 3: Repair and verify (zoom into box 3)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 16 | 2:05 | Step three: repair what software can fix. Realign, exposure, dehaze, white balance and denoise. | Five small tool sketches inside the box, each named as it is spoken. | `src/visiondoctor/repair/` |
| 17 | 2:12 | Every repair is bounded, and it only counts if a fresh scan and a fresh prediction confirm the recovery. | A loop arrow is drawn from "repair" back through "scan" to a big check mark; limits are written on the arrow ("≤ 10°"). | `repair/verify.py` |
| 18 | 2:19 | For drift, realignment restored 92 percent of the lost person detection accuracy, from 0.11 to 0.35 average precision. The clean camera scores 0.34. | Real before/after slider on the drifted frame. Three bars draw in: clean **0.34**, drifted **0.11**, repaired **0.35**. Label **"92% recovered"**. | `results/final/e4_repair.json` |
| 19 | 2:32 | If verification fails, the repair is rolled back, and the fault is escalated. | A red cross on the check mark; the arrow bends down to the "human" branch. Box 3 locks in. | Real trace (rollback then escalate) |

### 2:42–3:30 · Step 4: The agent (pan up to TOP: agent)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 20 | 2:42 | Step four: the agent. It reasons on Amazon Bedrock, but it never touches pixels or AWS directly. | A brain sketch labelled "Bedrock (Nova)", separated from the cameras by a drawn wall. | Live config |
| 21 | 2:49 | It acts only through thirteen MCP tools, and a guard checks every single call. Bounds, scope, budgets and approvals. | A toolbox with 13 small tool tags; a gate labelled **GUARD** in front of it; arrows pass through the gate. | `mcp_server/server.py`, `agent/guard.py` |
| 22 | 2:58 | In a live run, the model passed the wrong repair id. The guard blocked it. The agent re-planned, verified the fix, and only then closed the incident. | Zoom into the real trace screenshot: the blocked step glows terracotta, the next step verifies, then closes. | `results/final/example_trace_bedrock_guard_replan.json` |
| 23 | 3:09 | Physical faults, like a dirty lens, go to a person. They are ranked by predicted harm times camera importance, with evidence attached and faces blurred. | The real smudged frame → a ticket card with the description; the formula **"harm × importance"** is written on the card; a face in the evidence is visibly blurred. | Real incident card; YuNet blur |
| 24 | 3:20 | Across forty simulated incidents, it chose the right outcome 75 percent of the time, and cut operator alerts by 65 percent. | Pull back. Two numerals: **75%** correct, **–65%** alerts (40 → 14 bells). The agent part locks in. | `results/final/e5_agent_policy.json` |

### 3:30–4:00 · Step 5: Cloud (pan right to AWS)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 25 | 3:30 | Step five: the cloud. VisionDoctor is live on AWS Graviton4 in Mumbai, behind CloudFront and Cognito, with S3 and DynamoDB. | A cloud outline; inside it, small labelled boxes for each service are drawn in data-flow order. | `results/final/aws_outputs.json`, `aws_health.json` |
| 26 | 3:39 | One small Graviton instance scans twelve HD cameras 119 times a minute. That is about seven and a half dollars per million scans. | A speedometer sketch: **119 scans/min**; price tag **$7.55 / 1M scans**. | `results/final/bench_graviton4_c8g_large.json` |
| 27 | 3:47 | Operators see the whole fleet, approve a technician in one click, and can read every decision the agent made. | Zoom into the real live dashboard screenshot; the cursor clicks "Approve". | `docs/img/live_aws_dashboard.png`, `dashboard_incidents.png` |

### 4:00–4:30 · Who it helps, honesty, payoff (full pull back)

| # | ~Time | Narration | On screen | Proof |
|---|---|---|---|---|
| 28 | 3:55 | That helps security teams know which cameras really work, traffic teams trust their counts, factories catch drifting inspection cameras, and technicians arrive with the right tool. | Four sticky notes are drawn along the bottom, one per user group, each with a tiny sketch. | `docs/01_PROJECT_BRIEF.md` |
| 29 | 4:07 | It is not perfect. Crowded scenes still cause false alarms, and we report every failure case. | A small honest note in terracotta: **"crowds → false alarms"**, pointing at the crowd frame. | `results/final/e2_false_alarms.json`, REPORT §9 |
| 30 | 4:13 | Scan, predict, repair, verify, escalate. Cameras you can trust, so the AI on them can be trusted too. | Final pull back to the complete board; the loop lights up step by step in yellow. Takeaway: **"Trusted cameras, trusted AI."** | — |
| 31 | 4:21 | VisionDoctor. Built with OpenCV 5, on AWS. | The logo tile; under it, the GitHub link and the live URL in mono. | — |

**Estimated length: ~4:30.**

## Facts used and where they come from

| Fact in the video | Source |
|---|---|
| Philadelphia: 32% of sampled police cameras working properly | Philadelphia City Controller follow-up audit (docs/09) |
| Pittsburgh: 45 of 163 not fully operational | CBS/KDKA investigation (docs/09) |
| Baltimore: camera uptime not tracked | WMAR-2 on the Office of Legislative Audits report (docs/09) |
| Detectors fall to 30–60% of clean performance on corruptions | Michaelis et al. 2019 (docs/09) |
| 11 checks, 5 repairs, 13 MCP tools | This repository |
| Drift of 5° (severity 4) measured by ORB + USAC MAGSAC | `sim/faults.py`, `health/checks/drift.py` |
| 91% vs 24% recall at severity ≥ 3 | `results/final/e1_detection.json` |
| ρ = 0.50 against the true MOT17 AP drop | `results/final/e3_impact.json` |
| Realign: AP 0.114 → 0.346 (clean 0.338), 92% recovered | `results/final/e4_repair.json` |
| Guard blocked a wrong repair id, then the agent re-planned and verified | `results/final/example_trace_bedrock_guard_replan.json` |
| 75% correct outcome, 65% fewer alerts (40 incidents) | `results/final/e5_agent_policy.json` |
| 119 scans/min, $7.55 per 1M scans on Graviton4 c8g.large | `results/final/bench_graviton4_c8g_large.json` |
| Live on AWS Graviton4 in Mumbai (CloudFront, Cognito, S3, DynamoDB, Bedrock Nova) | `results/final/aws_outputs.json` |

## Build plan (after the script is approved)

1. Voice each line with edge-tts AriaNeural; time every shot to the real audio length.
2. One HTML file (1920×1080) where every style is computed from time inside `window.seek(t)`: no CSS animations,
   timers or carried state.
3. Render with Playwright (your Chrome) at 60 fps with 3 subframes per frame, blended with ffmpeg `tmix` for motion
   blur; mux the narration, a quiet music bed and line-by-line subtitles.
4. Before the full render, export one key frame per section and fix anything crowded or hard to read.
