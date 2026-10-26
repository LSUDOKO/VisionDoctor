# 08 — Submission Kit (Documentation & presentation 10%)

The competition requires: technical report; judge-accessible repo; pinned dependencies with build,
deploy and test instructions; architecture diagram (OpenCV 5 + AWS + COOL + agent); working web
endpoint or arranged live demo; video ≤ 5 minutes; evaluation evidence incl. failure cases.
Deadline per rules: **26 Oct 2026, 11:59 p.m. Pacific Time** (Devpost shows 27 Oct 12:15 p.m. IST — submit well before).

## 1. Technical report outline (`docs/REPORT.md`, export to PDF)
1. **Summary** (5 lines: problem, approach, headline results, awards targeted).
2. **Problem & users** — audit evidence (Philadelphia, Baltimore, Pittsburgh); research evidence
   (Michaelis 2019; Liu 2024); who benefits (docs/01 §3).
3. **Related work & novelty** — tamper detection (Saglam 2009, Huang 2014, Sidnev 2018, Sitara 2018),
   self-healing camera networks (Attarha 2026), camera condition monitoring (Wischow 2021); our four
   contributions.
4. **Architecture** — diagrams from docs/02 (system + agent loop), COOL components marked.
5. **OpenCV 5 implementation** — each check/repair with the exact functions; OpenCV 5 features used
   (USAC, features module, new DNN engine, rewritten warping, TRUCO contours, VLM, YuNet).
6. **AWS deployment** — services, IaC, security, observability; COOL version 3.1 and instance config.
7. **Agentic workflow** — tools, guard, human control; one full annotated trace.
8. **Evaluation** — E1–E7 tables/figures with CIs; COOL benchmark; ablations.
9. **Limitations & failure cases** — docs/06 §4 with examples.
10. **Responsible use** — privacy (no face recognition, face blur, retention), human approval,
    audit trail, misuse considerations (this is reliability tooling, not surveillance expansion).
11. **Reproducibility** — exact commands, versions, seeds, data licenses.
12. **References** — docs/09.

## 2. Five-minute video script (record at 1080p; captions on)
| Time | Visual | Narration (summary) |
|---|---|---|
| 0:00–0:25 | Team on camera; title card | Who we are; "A third of a city's cameras can be broken while dashboards show green." |
| 0:25–0:55 | Audit headlines + Michaelis chart | The problem: silent camera failures and silent AI degradation |
| 0:55–1:30 | Architecture diagram (COOL on Graviton highlighted) | How VisionDoctor works end to end |
| 1:30–3:00 | Live dashboard demo (docs/07 §3) | Drift auto-fixed with verification; smudge → VLM → approval; transient glare ignored |
| 3:00–3:30 | Agent trace viewer | OpenCV outputs changing the agent's next action (Agentic award) |
| 3:30–4:05 | COOL benchmark charts | Speedup and cost per 1M scans vs. stock OpenCV on Graviton and x86 (COOL award) |
| 4:05–4:40 | Evaluation results | Detection F1, false alarms/day, impact ρ, accuracy recovered, workload reduction |
| 4:40–5:00 | Limitations + responsible use + call to action | Honest limits; privacy by design; repo and endpoint links |

Keep it under 5:00 — the rules say "no more than five minutes".

## 3. Devpost submission text (fill in numbers from `results/summary.md`)
- **Tagline:** The AI that watches the cameras, so every other camera AI can be trusted.
- **Inspiration / What it does / How we built it / Challenges / Accomplishments / What we learned /
  What's next** — draw from docs/01 and REPORT.md.
- **Built with:** opencv-5, cool, aws-graviton, amazon-ec2, amazon-ecs-fargate, amazon-bedrock,
  amazon-dynamodb, amazon-s3, amazon-sqs, amazon-cognito, amazon-cloudfront, amazon-cloudwatch,
  aws-cdk, mcp, python, fastapi, react.
- Hashtag for social posts: `#OpenCVComp26`.

## 4. Final checklist
- [ ] Repo public or judge-accessible; README has setup/deploy/test commands that work from scratch
- [ ] `requirements.lock`, `package-lock.json`, CDK versions pinned
- [ ] Architecture diagram PNG (OpenCV 5, AWS, COOL, agent components)
- [ ] Working endpoint + judge login (or arranged screen-share)
- [ ] Video ≤ 5:00, public/unlisted, shows team, app working, architecture, results
- [ ] Evaluation evidence incl. failure cases (results/summary.md + REPORT.md)
- [ ] COOL evidence: version 3.1, instance type, build info with `/opt/cool` + KleidiCV, benchmark table
- [ ] Agentic evidence: workflow diagram, ≥ 1 full trace, task success/failure handling/observability/human control metrics
- [ ] Responsible-use section; data licenses; Gemma license note
- [ ] Budget alarm on; plan to `make down` and cancel Marketplace trial after judging
