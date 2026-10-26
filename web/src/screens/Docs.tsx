import { CHECKS, Icon, Tag } from "../ui";

const TOOLS: [string, string][] = [
  ["list_unhealthy_cameras", "Cameras whose latest scan found a fault, worst first."],
  ["scan_camera", "Run all 11 checks on a camera now and return the report."],
  ["diagnose", "Name the likely cause, localise it, and say which faults software can fix."],
  ["predict_ai_impact", "Label-free estimate of detector accuracy and its drop, with a 90% interval."],
  ["get_reference_comparison", "Reference, current and heat-map images for a camera."],
  ["apply_repair", "Apply one bounded correction: realign, exposure, dehaze, white balance or denoise."],
  ["verify_repair", "Re-scan after a repair and keep it only if it measurably helped."],
  ["rollback_repair", "Remove an applied correction."],
  ["describe_fault", "Plain-language description of the fault region for a technician."],
  ["request_human_approval", "Ask an operator to approve an action such as a technician dispatch."],
  ["create_maintenance_ticket", "Open a ticket with face-blurred evidence attached."],
  ["set_watch", "Re-scan a camera more often instead of acting on a low-impact fault."],
  ["close_incident", "Close the incident with an outcome."],
];

const API: [string, string, string][] = [
  ["GET", "/health", "Liveness, OpenCV version, agent and storage backend"],
  ["GET", "/api/config", "Public sign-in settings (no secrets)"],
  ["GET", "/api/summary", "Fleet KPIs: healthy %, predicted accuracy, incidents"],
  ["GET", "/api/cameras", "All cameras with status and thumbnail URL"],
  ["GET", "/api/cameras/{id}", "Camera detail: latest report, images, corrections, open incident"],
  ["GET", "/api/cameras/{id}/history", "Scan history (default 24 h)"],
  ["POST", "/api/cameras/{id}/scan", "Scan now"],
  ["POST", "/api/cameras/{id}/rollback", "Roll back a correction {repair_id}"],
  ["GET", "/api/incidents", "Incidents; ?state=open for the live queue"],
  ["POST", "/api/incidents/{id}/approve · reject · false_alarm", "Operator decisions (operator group)"],
  ["GET", "/api/traces · /api/traces/{id}", "Agent runs, step by step"],
  ["GET", "/api/bench · /api/metrics/ops", "Benchmark summary and live op timings"],
  ["GET", "/api/scenarios", "Available demo scenarios"],
  ["POST", "/api/sim/scenario · /api/sim/inject", "Drive the simulator (admin group)"],
];

const LOOP = [
  ["Observe", "A scheduled scan flags a camera. An incident opens and the agent is handed the camera id."],
  ["Investigate", "The agent re-scans, diagnoses and predicts the accuracy impact before deciding anything."],
  ["Act within bounds", "Fixable faults get one bounded repair, then verify_repair. A repair that doesn't help is rolled back."],
  ["Escalate or close", "Physical faults with high priority (drop × criticality) go to request_human_approval; low impact gets set_watch."],
];

const NAV = [["checks", "Health checks"], ["agent", "The agent loop"], ["tools", "MCP tools"], ["api", "API"], ["privacy", "Privacy"]];

function H({ id, eyebrow, children }: { id: string; eyebrow: string; children: React.ReactNode }) {
  return (
    <div id={id} className="scroll-mt-28">
      <div className="eyebrow">{eyebrow}</div>
      <h2 className="display mt-2 text-[28px] leading-tight">{children}</h2>
    </div>
  );
}

export default function Docs() {
  return (
    <div className="grid gap-10 lg:grid-cols-[13rem_minmax(0,1fr)]">
      <nav aria-label="On this page" className="hidden lg:block">
        <div className="sticky top-28 space-y-1">
          <div className="micro mb-2">On this page</div>
          {NAV.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="navlink w-full" onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{label}</a>
          ))}
        </div>
      </nav>
      <article className="min-w-0 space-y-16">
        <header>
          <span className="badge"><Icon name="eye" size={13} /> Docs</span>
          <h1 className="display mt-4 text-[clamp(34px,5vw,52px)] leading-none" style={{ letterSpacing: "0.04em" }}>How <span className="hl">VisionDoctor</span> works</h1>
          <p className="mt-5 max-w-2xl text-[17px] leading-relaxed text-ink">
            VisionDoctor watches a camera fleet with OpenCV 5, predicts how much downstream detector accuracy each fault costs
            without labels, applies bounded software repairs it then verifies, and escalates physical faults to a person.
            An agent (Amazon Bedrock Nova, or a deterministic policy) acts only through MCP tools behind a guard.
          </p>
        </header>

        <section className="space-y-6">
          <H id="checks" eyebrow="01 · Scan">The 11 health checks</H>
          <p className="max-w-2xl text-[15px] leading-relaxed">Each check scores 0–1 and maps to a severity from 0 (fine) to 5 (severe). Checks run in order and defer to each other, so one cause is reported once.</p>
          <div className="card overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Check</th><th>What it means</th><th>Software repair</th></tr></thead>
              <tbody>{Object.entries(CHECKS).map(([k, c]) => (
                <tr key={k}>
                  <td className="whitespace-nowrap"><span className="font-semibold text-ink">{c.label}</span><div className="mono text-[11px] muted">{k}</div></td>
                  <td className="text-body">{c.what}</td>
                  <td>{c.repair ? <Tag tone="mint" mono>{c.repair}</Tag> : <span className="text-xs muted">escalate</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </section>

        <section className="space-y-6">
          <H id="agent" eyebrow="02 · Decide">The agent loop</H>
          <ol className="grid gap-4 sm:grid-cols-2">
            {LOOP.map(([t, p], i) => (
              <li key={t} className={`note ${["", "mint", "teal", "yellow"][i]}`}>
                <span className="nk">step {i + 1}</span>
                <h3>{t}</h3>
                <p className="!text-[14.5px]">{p}</p>
              </li>
            ))}
          </ol>
          <p className="max-w-2xl text-[15px] leading-relaxed">
            The <b className="text-ink">guard</b> sits between the agent and every tool: an allowlist, parameter bounds, per-camera scope,
            call budgets and approval requirements. A blocked call is recorded in the trace with its reason. Every run is traced; see
            <a className="linkish ml-1" href="#/traces">Traces</a>.
          </p>
        </section>

        <section className="space-y-6">
          <H id="tools" eyebrow="03 · Act">MCP tools <span className="text-label">(13)</span></H>
          <div className="card overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Tool</th><th>Purpose</th></tr></thead>
              <tbody>{TOOLS.map(([n, d]) => <tr key={n}><td className="mono whitespace-nowrap text-ink">{n}</td><td>{d}</td></tr>)}</tbody>
            </table>
          </div>
        </section>

        <section className="space-y-6">
          <H id="api" eyebrow="04 · Integrate">API endpoints</H>
          <p className="max-w-2xl text-[15px] leading-relaxed">All <code className="inline">/api</code> routes take a Cognito ID token as <code className="inline">Authorization: Bearer …</code> when auth is enabled.</p>
          <div className="card overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Method</th><th>Path</th><th>Returns</th></tr></thead>
              <tbody>{API.map(([m, p, d]) => (
                <tr key={p}><td><Tag tone={m === "GET" ? "line" : "yellow"} mono>{m}</Tag></td><td className="mono whitespace-nowrap text-ink">{p}</td><td>{d}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </section>

        <section className="space-y-6">
          <H id="privacy" eyebrow="05 · Trust">Privacy</H>
          <ul className="grid gap-4 md:grid-cols-3">
            {[
              ["No face recognition", "VisionDoctor measures image quality only. It has no model that identifies, tracks or counts people."],
              ["Faces blurred", "A YuNet face detector mosaics every evidence image before it is stored or shown. If blurring fails, the image is withheld."],
              ["Humans approve", "The agent can recommend a technician dispatch but cannot send one. An operator approves, rejects or marks a false alarm."],
            ].map(([t, p]) => (
              <li key={t} className="card p-5"><Icon name="shield" size={20} /><h3 className="mt-3 font-semibold">{t}</h3><p className="mt-1.5 text-sm leading-relaxed">{p}</p></li>
            ))}
          </ul>
        </section>
      </article>
    </div>
  );
}
