# Deviations from spec

Every change from the spec: what, why, impact.

| # | What | Why | Impact |
|---|---|---|---|
| 1 | License stays **MIT** (spec says Apache-2.0) | Repository owner chose MIT in the initial commit | None for judging; both are permissive |
| 2 | MCP SDK **v2** (`mcp.server.mcpserver.MCPServer`) instead of `mcp.server.fastmcp.FastMCP` | `mcp` 2.3 renamed FastMCP (verified: import raises with a migration note) | Same tools/transports; agents call tools in-process via `MCPServer.call_tool` or over streamable HTTP |
| 3 | Datasets: MOT17 **sequence videos** (960×540) + labels and OpenCV `vtest.avi`; CDnet not used | Full CDnet (~11 GB) and MOT17 frames (5.9 GB) exceed this build machine (27 GB free disk, ~2 GB free RAM); CDnet server unreachable | Fewer, shorter sources; MOT17 labels scaled ×0.5; E7 (CDnet real faults) not run |
| 4 | Reference window = 60 frames from the first 8 s of each video (sim: spread over the clip loop) instead of ≥ 10 min | Videos are 18–80 s long | References see less variation → more false alarms on crowded scenes (MOT17-02 reported as failure case) |
| 5 | Severity uses **per-check bands** on interpretable metrics (e.g. % diagonal displacement, contrast loss) instead of one z-score table | z-scores with 60-frame std were unstable for geometric/photometric metrics; bands were calibrated on clean bursts (`results/calibration/thresholds.json`) | Thresholds documented in each check module |
| 6 | Drift magnitude from a **similarity transform refit on USAC-MAGSAC inliers** | Full homographies extrapolated spurious shear to frame corners when keypoints clustered | Realign still uses `warpPerspective`; residual < 0.5° in tests |
| 7 | Static mask = pixels that depart from the median in < 15% of calibration frames (not a temporal-std threshold) | Std masks removed all edges (compression flicker), leaving too few ORB keypoints | 2–9× more anchors |
| 8 | Noise check uses **temporal** σ (burst differences) as primary, Immerkaer as evidence | Immerkaer reads static fine texture as noise | Detection of real sensor noise works on textured scenes |
| 9 | Exposure repair = **gain + gamma** LUT (gain bounds 0.4–2.5, gamma 0.5–2.0) | Sensor gain faults are linear; gamma alone would need γ > 2 | New `exposure_gain_range` setting enforced by guard |
| 10 | Dehaze airlight kept achromatic | Tinted airlight estimates introduced colour casts | Verify passes without colour regressions |
| 11 | Verify also rejects repairs that create a new fault ≥ 3 (except realign border crop and dehaze noise amplification) | Over-strong denoise reads as defocus | Stricter than spec |
| 12 | Smudge needs persistence across 3 scans and static tiles; spider-web hint only in the dark | Crowds mimic local blur | Smudge needs ≥ 3 scans to fire |
| 13 | ALIKED/LightGlue not used; ORB is the matcher | Classes exist in OpenCV 5.0 (`cv2.ALIKED_create`, `cv2.LightGlueMatcher_create`) but need extra ONNX weights; ORB is sufficient for static cameras | Noted as upgrade |
| 14 | VLM: PaliGemma2 path implemented but **not executed** here; rule-based captions used | 3B model needs ~12 GB RAM; build machine has ~2 GB free | Incidents always get a description; `model` field says which produced it |
| 15 | Bedrock agent runs **Amazon Nova Lite** (`apac.amazon.nova-lite-v1:0`) instead of Claude | Anthropic models (Marketplace-billed) return `INVALID_PAYMENT_INSTRUMENT` on this AISPL account; Nova is first-party and credit-eligible | Live Nova traces on AWS (`results/final/example_trace_bedrock_guard_replan.json`); E5 numbers are the policy agent |
| 16 | `imagecorruptions` package not used; own OpenCV injectors cover all faults | Avoid extra heavy deps (scikit-image) | — |
| 17 | AWS: the full 7-stack architecture is synthesised only; a **lean** profile (1 Graviton4 instance + CloudFront + S3/DynamoDB/Cognito) is **deployed** in ap-south-1 | Full design costs ~$31/day; account has ~$96 credits. COOL Marketplace subscription is rejected for this AWS India (AISPL) account's card, so the instance runs stock OpenCV 5 | Live endpoint exists; no COOL measurements |
| 18 | COOL benchmark: only the local x86 configuration was run | No Graviton/COOL instance available without deploy | No COOL speedup claimed; BenchStack runs A/B/C when deployed |
| 19 | `mypy --strict` is a `make lint` target, not a blocking pre-commit hook | Keep iteration fast | Lint is advisory |
| 20 | Live simulator excludes MOT17-02 | Dense crowd at dusk gives too few static keypoints at 640 px (drift abstains) | Kept in offline eval as failure case |
| 21 | cdk-nag pinned to **2.38.2** | cdk-nag 3.x removed `NagSuppressions` (uses `Validations.of().acknowledge()` per finding) | Same AwsSolutions pack; suppressions with reasons are written to template metadata |
| 22 | Verify: when predicted loss < 0.15 the impact condition is "no predicted harm (≤ 0.1, ≈ predictor MAE)" instead of "recover ≥ 50% of the loss" | With small predicted losses the 50% test was decided by predictor noise (E5 first run: 0.60 correct) | E5 0.75 correct on final code; all runs reported in REPORT.md |
| 23 | Untrained-model fallback impact = 0.25 + 0.75 × worst check score (noise weighted half) | Keeps the agent deterministic when no model is trained; used by golden-trace tests on the synthetic scene, where the learned model is out of distribution | Golden traces test agent logic, not the learned model |
| 24 | Realign renders a reflected border for health analysis, black border for the downstream stream | The black crop was re-detected as occlusion/exposure on later scans | No spurious post-repair incidents |
| 25 | E5 bypasses the 10 incidents/min fleet rate limit | The evaluation replays incidents faster than real time | Rate limit still enforced in the service |
| 26 | Architecture PNGs drawn with OpenCV (`scripts/draw_architecture.py`), Mermaid sources kept | mermaid-cli needs a headless Chromium download; external renderers not used | Diagrams in docs/img |
| 27 | `is_cool` = cv2 installed under `/opt/cool` only | The official OpenCV 5 aarch64 wheel also reports KleidiCV in `getBuildInformation()` (observed on Graviton4), so KleidiCV is not proof of COOL | Earlier detection would have falsely claimed COOL; fixed before any claim |
| 28 | Guard: `verify_repair`/`rollback_repair` must use a repair id applied in this run; `close_incident(auto_fixed)` requires every applied repair verified | Live Nova run passed the repair *name* as id and then closed as auto-fixed | Nova now gets blocked, re-plans and verifies (trace saved) |
