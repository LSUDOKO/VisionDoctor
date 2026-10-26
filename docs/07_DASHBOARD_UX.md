# 07 — Dashboard and User Experience (10%)

React + Vite + TypeScript + Tailwind; Recharts for charts; React Query for data; Cognito Hosted UI
(or Amplify Auth library — **VERIFY** current package) for login. Built to `web/dist`, deployed by WebStack.

## 1. Screens
1. **Fleet overview** — grid of camera tiles (live thumbnail, name, status chip, predicted AI accuracy,
   last scan). Status uses **icon + text + color** (✓ Healthy, ◐ Watch, ▲ Degraded, ✕ Failed,
   ⟳ Repairing) — never color alone. Filters by site/status; summary bar: % healthy, predicted fleet
   accuracy, open incidents, auto-fixed today.
2. **Camera detail** — side-by-side *reference vs. current* with a draggable before/after slider;
   tile heat-map overlay toggle; health timeline (24 h) per check; predicted accuracy line;
   applied correction profile with **Rollback** button.
3. **Incident queue** — sorted by priority (predicted drop × criticality). Each card: fault types,
   evidence crop (face-blurred), VLM description, predicted impact, agent recommendation, buttons
   **Approve dispatch / Reject / Mark false alarm**. Approval records the Cognito user and time.
4. **Agent trace viewer** — timeline of steps: tool, key numbers, decision reason, guard verdict,
   latency; highlights the step where an OpenCV result changed the plan (award evidence).
5. **Performance** — COOL vs. baseline charts from `/bench`, CloudWatch-style scan latency,
   cost per 1M scans.
6. **Demo control** (admin only) — start a fault scenario from `sim/scenarios/*.yaml` for live judging.

## 2. Accessibility and quality
WCAG 2.2 AA contrast; full keyboard navigation and visible focus; ARIA labels on images
("Camera 7 current view, haze detected, severity 3"); respects `prefers-reduced-motion`;
dark/light themes; responsive down to 375 px (technicians use phones); every number has units
and a tooltip explaining it in plain language ("Predicted accuracy: how well the detection AI on
this camera is likely working right now, estimated without labels").

## 3. Demo flow for judges (also the video's core, ≈ 90 s)
1. Fleet all green → start `demo.yaml`.
2. cam-03 turns ▲ (drift) → trace shows scan → impact (0.79→0.48) → realign → verify → ✓ auto-fixed.
3. cam-01 smudge → VLM: "a blurry smear across the lower left of the lens" → approval card → approve → ticket.
4. cam-08 glare transient → closed as transient (no alert) — shows false-alarm control.
5. Performance tab: COOL vs. baseline speedup and cost.

## 4. Judge access
A Cognito user `judge@…` with the `operator` group (credentials in the private submission notes,
not the repo). The landing page links to the video, report and GitHub repo.
