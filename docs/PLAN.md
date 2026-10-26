# Implementation Plan (deadline 26 Oct 2026, 23:59 PT)

Order follows CLAUDE.md §4 "minimum winning entry" first, upgrades after.

| # | Phase | Deliverable | Acceptance |
|---|---|---|---|
| 0 | Scaffold | pyproject, lock, Makefile, `cv_runtime` (OpenCV ≥ 5 assert, COOL detection) | `make test`; `python -m visiondoctor.cv_runtime` |
| 2 | Health engine | reference learning + 11 checks + scan + heat map | unit tests per check (synthetic faults sev ≥ 3 detected, clean frames quiet) |
| 3 | Repairs | realign, exposure, dehaze, white balance, denoise + verify | drift ≤ 8° recovered to < 0.5°; check scores improve |
| 1 | Simulator | fault injectors, YAML scenarios, FleetSimulator, truth log | `make demo-sim` |
| 4 | Impact predictor | YOLOX (OpenCV 5 DNN, ENGINE_NEW), agreement F1, HGB regressor | `make eval-impact` Spearman ρ reported |
| 5 | MCP + agents | FastMCP tools, PolicyAgent, BedrockAgent (Converse), guard, traces | golden-trace tests |
| 6a | API | FastAPI routes per docs/02 §5, local backend | `make demo` |
| 7 | Privacy + VLM | YuNet face blur on evidence; PaliGemma2 wrapper with fallback | tests |
| 8 | Dashboard | React/Vite/TS/Tailwind fleet, incidents, trace viewer, performance | Playwright smoke |
| 6b/c | AWS | CDK stacks + cdk-nag, observability | `cdk synth` (deploy only after owner approval) |
| 9 | Eval + report | E1–E5, local bench, figures, REPORT.md from `results/` | every number traced to `results/` |

Constraints on this build machine (16 cores, ~2 GB free RAM, 27 GB disk): small datasets,
no local VLM inference, x86 only (COOL numbers come only from a Graviton run).
