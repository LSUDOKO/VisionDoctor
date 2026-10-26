# Five-minute video script (≤ 5:00, 1080p, captions on)

Numbers in brackets are filled from `results/summary.md` — never quote a number that is not there.

| Time | Visual | Narration |
|---|---|---|
| 0:00–0:25 | Team on camera; title card "VisionDoctor" | "Audits in Philadelphia, Baltimore and Pittsburgh found that 12–68% of city cameras were not working — while dashboards showed green. We built VisionDoctor: the AI that watches the cameras, so every other camera AI can be trusted." |
| 0:25–0:55 | Audit headlines; detector-robustness chart (Michaelis 2019) | "Cameras drift, fog up, get dirty or freeze, and the detection AI on top silently degrades — to 30–60% of its clean performance in published benchmarks. Today nobody measures that loss." |
| 0:55–1:30 | `docs/img/architecture.png`, COOL box highlighted | "Eleven OpenCV 5 checks run on AWS Graviton with COOL. A label-free predictor estimates how much accuracy the detector has lost. An agent on Amazon Bedrock acts only through MCP tools, behind a guard, and asks a human before anything physical." |
| 1:30–3:00 | Live dashboard: Demo tab → `demo` scenario | Drift on cam-03 → tile turns ▲ → trace: scan (rotation, displacement) → predicted accuracy drop → realign → verify → ✓ auto-fixed. Smudge on cam-01 → description → approval card → Approve → ticket → camera recovers. Transient glare on cam-08 closes as transient with no alert. |
| 3:00–3:30 | Trace viewer, "OpenCV result changed the plan" badges | "Every arrow is a recorded tool call. Here the scan's homography numbers decide the repair; here verification fails and the agent rolls back and escalates; here the guard blocks a 25° realign." |
| 3:30–4:05 | Performance tab | COOL vs stock OpenCV 5 vs x86: [speedup per op], [scans/min], [$ per 1M scans] — only if the Graviton benchmark has been run; otherwise show local numbers and say so. |
| 4:05–4:40 | `results/figs/*` | Detection recall at severity ≥ 3 [E1], false incidents per camera-day [E2], impact ρ vs true MOT17 AP drop [E3], accuracy recovered [E4], operator workload reduction [E5]. |
| 4:40–5:00 | Limitations slide; repo + endpoint | "Crowded scenes and legitimate scene changes are our main failure cases. No face recognition, faces blurred, humans approve every physical action. Code, data licences and every number are in the repo." |
