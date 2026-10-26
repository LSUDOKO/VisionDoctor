# VisionDoctor — Build Pack for Claude Code

> **The AI that watches the cameras, so every other camera AI can be trusted.**
> Entry for the **OpenCV AI Competition 2026, powered by AWS** — targets the Grand Prize,
> the **Agentic Vision Award** and the **Best Use of COOL Award**.

This folder is a complete, implementation-ready specification. Hand it to Claude Code and it
has everything it needs to build a fully working project: architecture, exact OpenCV 5 APIs,
agent + MCP design, AWS/COOL deployment, evaluation protocol, UI, and submission materials.

## How to use this pack with Claude Code

1. Unzip into an empty folder, e.g. `~/visiondoctor/`.
2. Open a terminal there and run `claude`.
3. Paste this prompt:

   ```
   Read CLAUDE.md first, then every file in docs/ in numeric order.
   Build VisionDoctor exactly as specified, phase by phase. After each phase,
   run that phase's acceptance checks and show me the results before moving on.
   Never invent an API: verify every OpenCV 5, MCP, boto3 and CDK call against
   the official docs (use the Context7 MCP or docs.opencv.org/5.x) and record
   any deviation from this spec in docs/DEVIATIONS.md.
   ```

4. Have AWS credentials configured (`aws configure`) before Phase 6 (deployment).

## What's inside

| File | Purpose |
|---|---|
| `CLAUDE.md` | Master instructions for Claude Code: rules, repo layout, phased build plan, acceptance checks |
| `docs/01_PROJECT_BRIEF.md` | Problem, evidence, innovation, impact, judging-criteria mapping |
| `docs/02_ARCHITECTURE.md` | System + agent diagrams (Mermaid), components, data model, APIs |
| `docs/03_OPENCV5_HEALTH_ENGINE.md` | Every health check, repair and model, with OpenCV 5 calls and code skeletons |
| `docs/04_AGENT_AND_MCP.md` | MCP tool server, Bedrock agent loop, policy guard, traces, human approval |
| `docs/05_AWS_AND_COOL.md` | COOL AMI/Docker facts, AWS architecture, CDK stacks, security, COOL benchmark |
| `docs/06_EVALUATION.md` | Datasets, fault injection, metrics, ablations, failure-case reporting |
| `docs/07_DASHBOARD_UX.md` | Web dashboard screens, accessibility, demo flow |
| `docs/08_SUBMISSION_KIT.md` | Technical report outline, 5-minute video script, final checklist |
| `docs/09_REFERENCES.md` | Every source, paper, dataset, model and doc link used |

## Facts verified while writing this pack (October 2026)

- **OpenCV 5**: new graph DNN engine (`engine=` param on `readNet*`, `OPENCV_FORCE_DNN_ENGINE`),
  `features2d` renamed to `features` (ALIKED, DISK, LightGlue added), `calib3d` split into
  `geometry`/`calib`/`stereo`/`ptcloud`, USAC default for robust estimation, faster
  `warpPerspective`/`remap`, TRUCO `findContours`, native VLM sample (`samples/dnn/vlm_inference.py`,
  PaliGemma2-3B ONNX + `cv.dnn.Tokenizer`), ML module moved to contrib, model zoo on
  `huggingface.co/opencv`. Python keeps `cv2.<func>()` names.
- **COOL** (AWS Marketplace "Cloud Optimized OpenCV For AWS Graviton4"): version **3.1**, built on
  **OpenCV 5.0** with **Arm KleidiCV**; Ubuntu 24.04 Arm AMI; installed at `/opt/cool`; Python venvs
  `/opt/cool/venvs/python_3.10|3.11|3.12`; C++ SDK at `/opt/cool/cpp_sdk`; recommended
  `m8g.4xlarge`, compatible `c8g/m8g/r8g`; 7-day free trial; benchmarked on 78 imgproc/core/IO
  functions vs. default OpenCV 5.0.0. A **Docker** variant exists for ECS/EKS, plus Graviton2/3/5 builds.

Anything not on this list is marked **VERIFY** in the docs — Claude Code must check it before use.
