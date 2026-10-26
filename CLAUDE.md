# CLAUDE.md — Build Instructions for VisionDoctor

You are building **VisionDoctor**: an agentic camera-health system. It monitors a fleet of
cameras with OpenCV 5, diagnoses faults (drift, defocus, dirty lens, haze, glare, occlusion,
color cast, noise, freeze, exposure, vibration), **predicts how much downstream AI accuracy
has been lost without labels**, repairs software-fixable faults, **verifies each repair by
re-scanning**, and escalates physical faults to a human with evidence. The heavy vision
workload runs on **AWS Graviton with COOL**; the agent runs on **Amazon Bedrock** and calls
OpenCV through an **MCP tool server**.

Read every file in `docs/` in numeric order before writing code.

---

## 1. Non-negotiable rules

1. **Never invent an API.** Before using any OpenCV 5, MCP SDK, boto3, Bedrock, CDK or React
   API, confirm it in official docs (Context7 MCP, `docs.opencv.org/5.x`, `help(cv2.X)`,
   AWS docs). Items marked **VERIFY** in the docs are known-uncertain — check them first.
2. **OpenCV 5 only.** Assert at startup: `int(cv2.__version__.split('.')[0]) >= 5`, else exit
   with a clear error. Never silently fall back to OpenCV 4.
3. **Local-first, cloud-second.** Every feature must run locally with `VD_BACKEND=local`
   (filesystem + SQLite, no AWS). `VD_BACKEND=aws` swaps in S3/DynamoDB/SQS/Bedrock behind the
   same interfaces. Judges must be able to reproduce results without an AWS account.
4. **Agent works without an LLM.** If Bedrock is unavailable, `VD_AGENT=policy` runs the
   deterministic policy agent (same tools, same trace format). The LLM agent is `VD_AGENT=bedrock`.
5. **Pin everything.** `requirements.lock` (pip-tools or uv) with exact versions and hashes;
   `package-lock.json` for the web app; CDK versions pinned.
6. **Every claim gets a test or a measurement.** No number goes in the report unless a script
   in `eval/` or `bench/` produced it and saved it to `results/`.
7. **Record deviations.** If something in this spec is wrong or impossible, do the closest
   correct thing and log it in `docs/DEVIATIONS.md` (what, why, impact).
8. **Security defaults.** No secrets in code; IAM least privilege; S3 Block Public Access +
   SSE; Cognito auth on the API; no face recognition anywhere; evidence images get faces
   blurred (see docs/03 §7).
9. After each phase, run its acceptance checks, show the output, and commit with a
   conventional commit message.

---

## 2. Tech stack (pin exact versions in lock files)

| Layer | Choice |
|---|---|
| Language | Python 3.12 (matches COOL venv `python_3.12`) |
| Vision | OpenCV 5.x (COOL build on Graviton; stock OpenCV 5 elsewhere) — **VERIFY** whether `pip install opencv-python==5.*` exists; if not, build 5.x from source in `docker/Dockerfile.x86-baseline` |
| Numerics | numpy, scipy (minimal), scikit-learn (impact regressor — OpenCV's ml module moved to contrib) |
| API | FastAPI + uvicorn, pydantic v2 |
| MCP | Official `mcp` Python SDK (`from mcp.server.fastmcp import FastMCP`) — **VERIFY** current import path |
| Agent LLM | Amazon Bedrock **Converse API** with tool use (`bedrock-runtime` `converse`) — model chosen at deploy time from `aws bedrock list-inference-profiles` (prefer a Claude Sonnet profile); never hardcode a model ID |
| Storage | local: filesystem + SQLite; aws: S3 + DynamoDB |
| Queue | local: in-process asyncio queue; aws: SQS |
| Web | React + Vite + TypeScript + Tailwind; charts with Recharts |
| IaC | AWS CDK v2 (Python) |
| Observability | structlog JSON logs, OpenTelemetry → CloudWatch (ADOT), CloudWatch EMF metrics |
| Tests | pytest, pytest-asyncio, hypothesis (for metric invariants), Playwright (1 smoke test) |

---

## 3. Repository layout (create exactly this)

```
visiondoctor/
├── CLAUDE.md, README.md, LICENSE (Apache-2.0)
├── pyproject.toml, requirements.in, requirements.lock
├── Makefile                      # make setup | data | models | test | demo | bench | eval | deploy
├── src/visiondoctor/
│   ├── config.py                 # pydantic Settings; VD_BACKEND, VD_AGENT, thresholds
│   ├── cv_runtime.py             # OpenCV 5 assertion, build-info capture, COOL detection
│   ├── health/
│   │   ├── reference.py          # reference-frame learning per camera
│   │   ├── checks/               # one module per check (see docs/03 §3)
│   │   │   ├── sharpness.py  drift.py  vibration.py  haze.py  glare.py
│   │   │   ├── exposure.py   occlusion.py  smudge.py  color_cast.py
│   │   │   ├── noise.py      freeze.py
│   │   ├── scan.py               # runs all checks → HealthReport
│   │   └── heatmap.py            # tile-wise quality map for UI/evidence
│   ├── repair/                   # realign.py exposure.py dehaze.py white_balance.py denoise.py
│   ├── impact/                   # detector.py (DNN), features.py, predictor.py (sklearn), agreement.py
│   ├── vlm/describe.py           # OpenCV 5 VLM (PaliGemma2) wrapper, lazy-loaded
│   ├── privacy/face_blur.py      # YuNet face detection → blur on evidence images
│   ├── mcp_server/server.py      # FastMCP tools (docs/04 §2)
│   ├── agent/                    # loop.py policy.py bedrock.py guard.py prompts.py trace.py
│   ├── api/                      # FastAPI app: fleet, cameras, incidents, traces, approvals
│   ├── sim/                      # fleet simulator + fault injection (docs/06 §2)
│   ├── storage/                  # interfaces + local/aws implementations
│   └── observability/            # logging, metrics, tracing setup
├── web/                          # React dashboard (docs/07)
├── infra/                        # CDK app (docs/05)
├── bench/                        # COOL benchmark harness (docs/05 §6)
├── eval/                         # evaluation scripts (docs/06)
├── scripts/                      # download_data.sh, download_models.sh, make_report_figs.py
├── docker/                       # Dockerfile.arm64-cool, Dockerfile.x86-baseline, compose.yaml
├── tests/                        # unit + integration + golden traces
├── results/                      # generated JSON/CSV/PNG (gitignored except final)
└── docs/                         # this spec + DEVIATIONS.md + REPORT.md
```

---

## 4. Phased build plan with acceptance checks

Build in this order. Do not start a phase until the previous phase's checks pass.
If time is short, Phases 1–5 + 6a + 8 are the **minimum winning entry**; 7 and 6b–c are upgrades.

### Phase 0 — Scaffold
- Create layout, `pyproject.toml`, lock files, Makefile, pre-commit (ruff, black, mypy --strict on `src/`).
- `cv_runtime.py`: assert OpenCV ≥ 5; expose `build_info()` returning `cv2.getBuildInformation()`,
  `cv2.__file__`, and `is_cool = "/opt/cool" in cv2.__file__ or "KleidiCV" in build_info`
  (**VERIFY** the exact string KleidiCV appears as in `getBuildInformation()` on the COOL AMI).
- ✅ `make setup && make test` passes; `python -m visiondoctor.cv_runtime` prints version + COOL flag.

### Phase 1 — Data, models, simulator
- `scripts/download_data.sh`: CDnet 2014 subsets + MOT17 static sequences (docs/06 §1).
- `scripts/download_models.sh`: detector ONNX, YuNet, VLM ONNX parts (docs/03 §6–8).
- `sim/`: `FleetSimulator` streams N virtual cameras from video files at configurable FPS and
  injects scheduled faults from a YAML scenario (docs/06 §2). Writes ground-truth fault log.
- ✅ `make demo-sim` runs 12 cameras for 60 s; ground-truth log written; frames visible in `results/sim/`.

### Phase 2 — Health engine (OpenCV 5 core — 30% of the score lives here)
- Implement reference learning and all 11 checks exactly per docs/03 §2–3, each returning a
  typed `CheckResult(score: float 0..1, severity, evidence: dict, region_mask: optional)`.
- `scan.py` combines into `HealthReport` with an overall health score and a tile heat map.
- ✅ Unit tests: each check detects its own synthetic fault at severity ≥ 3 with recall ≥ 0.9
  and fires < 1% on clean CDnet "baseline" frames. Scan latency per 1080p frame reported.

### Phase 3 — Repairs + verification
- Implement repairs per docs/03 §4, each with bounds and a `verify()` that re-scans.
- ✅ Tests: realign recovers injected drift ≤ 8° to < 0.5° residual; dehaze/exposure/white-balance
  improve their check scores; every repair returns before/after metrics.

### Phase 4 — AI-impact predictor (the key innovation)
- `impact/detector.py`: OpenCV 5 DNN detector (new engine) per docs/03 §6.
- `impact/agreement.py`: label-free target = F1 between detections on the degraded frame and
  on the camera's clean reference window (docs/03 §6.3).
- `impact/predictor.py`: train a `HistGradientBoostingRegressor` from health features →
  agreement; also validate against true mAP drop on MOT17 ground truth.
- ✅ `make eval-impact`: Spearman ρ ≥ 0.7 between predicted and true accuracy drop on held-out
  sequences (report the real number whatever it is; tune before giving up).

### Phase 5 — MCP server + agent
- `mcp_server/server.py` exposing the tools in docs/04 §2 (stdio and streamable-HTTP transports).
- `agent/policy.py` deterministic agent; `agent/bedrock.py` LLM agent; both use `guard.py`.
- `agent/trace.py` writes the trace schema in docs/04 §5.
- ✅ Golden-trace tests: for 6 scripted incidents (drift, haze, smudge, occlusion, freeze, false
  alarm) the policy agent produces the expected action sequence; the Bedrock agent (if
  credentials exist) reaches the same final outcome; guard blocks an out-of-bounds repair.

### Phase 6 — API, AWS deployment, COOL
- 6a: FastAPI (docs/02 §5) + local docker compose. ✅ `make demo` opens a working dashboard API.
- 6b: CDK stacks per docs/05 §4. ✅ `cdk synth` clean; `cdk deploy` succeeds; `/health` endpoint
  green behind Cognito; a scan job runs on the COOL Graviton worker and logs `is_cool=true`.
- 6c: Observability: CloudWatch dashboard + alarms (docs/05 §5).

### Phase 7 — VLM explanation + privacy
- `vlm/describe.py` per docs/03 §8 (runs only on escalations; cached; timeout-guarded).
- `privacy/face_blur.py` YuNet blur on every evidence image before storage.
- ✅ VLM produces a caption for a cropped fault region in < 60 s on c8g; evidence images contain no unblurred faces in tests.

### Phase 8 — Web dashboard (docs/07)
- ✅ Playwright smoke test: fleet grid loads, an incident can be approved, trace viewer renders.

### Phase 9 — Evaluation, COOL benchmark, report assets
- Run `make bench` (docs/05 §6) and `make eval` (docs/06). Generate all figures.
- Fill `docs/REPORT.md` from docs/08 §1 using only numbers in `results/`.
- ✅ All tables in REPORT.md trace to a file in `results/`.

---

## 5. Coding conventions
- Type hints everywhere; pydantic models for all tool inputs/outputs; no bare `except`.
- Every OpenCV function call that matters for the report is wrapped by a timing decorator that
  emits a metric (`vd.op_ms{op=...}`) — this powers the COOL comparison.
- Images are BGR `np.ndarray` uint8 internally; convert once at the boundary.
- Thresholds live in `config.py` with docstrings citing how they were calibrated (docs/03 §9).
- Deterministic seeds for simulator, training and evaluation.

## 6. Definition of done
- `make setup data models test demo` works on a clean Ubuntu 24.04 machine (x86 or Arm).
- Deployed endpoint reachable by judges (Cognito test user documented in the submission).
- `results/` contains benchmark + evaluation outputs; REPORT.md complete; video script ready.
