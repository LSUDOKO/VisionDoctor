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
| 15 | Bedrock agent coded and wired, **live runs failed**: account returned `AccessDeniedException ... INVALID_PAYMENT_INSTRUMENT` for Anthropic models and daily-token throttling for Nova | Account billing state, not code | Runner falls back to the policy agent automatically (trace marks it); E5 reports the policy agent |
| 16 | `imagecorruptions` package not used; own OpenCV injectors cover all faults | Avoid extra heavy deps (scikit-image) | — |
| 17 | AWS: `cdk synth` only; **not deployed** | Owner asked to synth only; COOL needs a Marketplace subscription (human step) | No live endpoint/COOL numbers yet; `make deploy` documented |
| 18 | COOL benchmark: only the local x86 configuration was run | No Graviton/COOL instance available without deploy | No COOL speedup claimed; BenchStack runs A/B/C when deployed |
| 19 | `mypy --strict` is a `make lint` target, not a blocking pre-commit hook | Keep iteration fast | Lint is advisory |
| 20 | Live simulator excludes MOT17-02 | Dense crowd at dusk gives too few static keypoints at 640 px (drift abstains) | Kept in offline eval as failure case |
