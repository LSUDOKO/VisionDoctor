import { Icon, Logo, ThemeToggle, type Theme } from "../ui";

const REPO = "https://github.com/LSUDOKO/VisionDoctor";

const STEPS = [
  { n: "01", t: "Scan", tone: "", foot: "11 OpenCV 5 checks", p: <>Every frame is compared with a learned reference: drift, vibration, haze, glare, exposure, occlusion, smudge, colour cast, noise, sharpness, freeze.</> },
  { n: "02", t: "Diagnose", tone: "mint", foot: "severity 0–5 per check", p: <>Checks defer to each other so one cause is named once. A heat map shows <em>where</em> in the picture the fault lives.</> },
  { n: "03", t: "Predict impact", tone: "teal", foot: "label-free", p: <>A regressor estimates how much accuracy the detector on that camera is losing right now, without a single ground-truth label.</> },
  { n: "04", t: "Repair & verify", tone: "blush", foot: "realign · exposure · dehaze · WB · denoise", p: <>Bounded software corrections are applied, then the camera is re-scanned. A repair that doesn&apos;t measurably help is rolled back.</> },
  { n: "05", t: "Escalate", tone: "yellow", foot: "human approval", p: <>Physical faults go to a person, ranked by predicted drop × camera criticality, with face-blurred evidence attached.</> },
];

const RESULTS = [
  { v: "0.911", cap: "fault recall at severity ≥ 3", sub: "vs 0.239 classic tamper baseline" },
  { v: "92%", cap: "lost detector AP recovered", sub: "verified realign · 0.114 → 0.346" },
  { v: "ρ 0.50", cap: "label-free impact vs true AP drop", sub: "Spearman, MOT17 labels" },
  { v: "65%", cap: "fewer operator alerts", sub: "policy agent · 75% correct outcome" },
  { v: "119", cap: "scans / min on Graviton4", sub: "c8g.large · 2 vCPU · 1080p" },
  { v: "$7.55", cap: "per 1M scans", sub: "on-demand pricing, Mumbai" },
];

function Sketch({ kind, className, size }: { kind: "arrow" | "star" | "loop"; className: string; size: number }) {
  const d = {
    arrow: "M6 40c18-14 40-20 64-12M58 18l13 10-15 7",
    star: "M30 6l5 16 17 1-13 10 5 17-14-10-14 10 5-17L8 23l17-1z",
    loop: "M8 50c10-30 40-40 52-22 10 15-12 26-20 14-8-13 14-30 40-24",
  }[kind];
  return (
    <svg className={`sketch ${className}`} width={size} height={size * 0.75} viewBox="0 0 80 60" fill="none" stroke="currentColor"
      strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={d} />
    </svg>
  );
}

export default function Landing({ theme, toggleTheme, signedIn }: { theme: Theme; toggleTheme: () => void; signedIn: boolean }) {
  return (
    <div className="lp">
      <div className="navwrap">
        <nav className="navpill" aria-label="Primary">
          <Logo href="#/about" />
          <div className="navlinks hidden md:flex">
            <a className="navlink" href="#how" onClick={(e) => { e.preventDefault(); document.getElementById("how")?.scrollIntoView({ behavior: "smooth" }); }}>How it works</a>
            <a className="navlink" href="#results" onClick={(e) => { e.preventDefault(); document.getElementById("results")?.scrollIntoView({ behavior: "smooth" }); }}>Results</a>
            <a className="navlink" href="#responsible" onClick={(e) => { e.preventDefault(); document.getElementById("responsible")?.scrollIntoView({ behavior: "smooth" }); }}>Responsible use</a>
            <a className="navlink" href="#/docs">Docs</a>
          </div>
          <div className="navright ml-auto md:ml-0">
            <ThemeToggle theme={theme} toggle={toggleTheme} />
            <a className="btn primary sm" href="#/fleet" data-testid="landing-open"><span className="arrow flex items-center gap-2">{signedIn ? "Console" : <><span className="sm:hidden">Console</span><span className="hidden sm:inline">Open console</span></>}</span></a>
          </div>
        </nav>
      </div>

      <header className="lphero lpwrap">
        <Sketch kind="arrow" className="left-[3%] top-[130px] hidden lg:block" size={140} />
        <Sketch kind="star" className="right-[7%] top-[96px] hidden lg:block" size={80} />
        <Sketch kind="loop" className="bottom-[30px] right-[12%] hidden lg:block" size={150} />
        <div className="rise">
          <span className="badge"><Icon name="eye" size={13} /><span>Camera health for AI fleets<span className="hidden sm:inline"> · OpenCV 5 · AWS Graviton4</span></span></span>
          <h1 className="lph1">The AI that watches the <span className="hl wash">cameras</span>.</h1>
          <p className="lpsub">
            So every other camera AI can be trusted. VisionDoctor spots drift, haze, glare and nine other faults,
            predicts how much your detector is losing, fixes what software can, verifies the fix, and sends a person
            for the rest.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <a className="btn primary big" href="#/fleet" data-testid="landing-cta"><span className="arrow flex items-center gap-2">Open console</span></a>
            <a className="btn pastel big" href="#how" onClick={(e) => { e.preventDefault(); document.getElementById("how")?.scrollIntoView({ behavior: "smooth" }); }}>How it works</a>
          </div>
          <p className="mt-3 text-[13px] muted">Agent acts only through guarded MCP tools · every decision traced</p>
        </div>
      </header>

      <section id="how" className="lpsec lpwrap">
        <div className="eyebrow">How it works</div>
        <h2 className="lph2">Five moves, from a bad frame to a <span className="hl">trusted</span> one.</h2>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {STEPS.map((s) => (
            <li key={s.n} className={`note ${s.tone} min-h-[260px]`}>
              <span className="nk">{s.n}</span>
              <h3>{s.t}</h3>
              <p className="!text-[14.5px]">{s.p}</p>
              <span className="nfoot">{s.foot}</span>
            </li>
          ))}
        </ol>
      </section>

      <section id="results" className="lpsec lpwrap">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="eyebrow">Results</div>
            <h2 className="lph2">Numbers we measured, not promised.</h2>
          </div>
          <a className="linkish text-sm" href={`${REPO}/blob/main/docs/REPORT.md`} target="_blank" rel="noreferrer">measured, see report ↗</a>
        </div>
        <div className="mt-10 grid gap-x-8 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {RESULTS.map((r) => (
            <div key={r.cap} className="result">
              <div className="big-num text-[clamp(44px,5.4vw,68px)]">{r.v}</div>
              <div className="mt-3 text-[15px] font-semibold text-ink">{r.cap}</div>
              <div className="micro mt-1">{r.sub}</div>
            </div>
          ))}
        </div>
        <div className="builtwith mt-14 flex flex-wrap items-center gap-x-6 gap-y-3" aria-label="Built with">
          <span className="!font-sans !text-xs">Built with:</span>
          <span>OpenCV 5</span><span>AWS Graviton4</span><span>Amazon Bedrock</span><span>MCP</span><span>Amazon Cognito</span><span>React</span>
        </div>
      </section>

      <section id="responsible" className="lpsec lpwrap">
        <div className="eyebrow">Responsible use</div>
        <h2 className="lph2">It looks at the camera, never at people.</h2>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <article className="card p-6">
            <Icon name="shield" size={22} />
            <h3 className="mt-4 text-lg font-semibold">No face recognition</h3>
            <p className="mt-2 text-[15px] leading-relaxed">VisionDoctor measures image quality. It does not identify, track or count people, and has no model that could.</p>
          </article>
          <article className="card p-6">
            <Icon name="eye" size={22} />
            <h3 className="mt-4 text-lg font-semibold">Faces blurred in evidence</h3>
            <p className="mt-2 text-[15px] leading-relaxed">Every evidence image is face-mosaicked before it is stored or shown. If blurring fails, the image is withheld.</p>
          </article>
          <article className="card p-6">
            <Icon name="user" size={22} />
            <h3 className="mt-4 text-lg font-semibold">A human approves dispatch</h3>
            <p className="mt-2 text-[15px] leading-relaxed">The agent can only call allow-listed tools within bounds. Sending a technician always waits for a person.</p>
          </article>
        </div>
      </section>

      <div className="lpwrap">
        <div className="band mt-24 px-6 py-14 text-center">
          <h2 className="lph2">See which of your cameras the AI shouldn&apos;t trust.</h2>
          <p className="mx-auto mt-3 max-w-xl text-[17px]">Live fleet, incident queue and full agent traces in the console.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <a className="btn primary big" href="#/fleet"><span className="arrow flex items-center gap-2">Open console</span></a>
            <a className="btn big" href="#/docs">Read the docs</a>
          </div>
        </div>
        <footer className="mt-12 flex flex-wrap items-center justify-between gap-4 border-t border-hairline py-8">
          <Logo href="#/about" size={28} />
          <nav aria-label="Footer" className="flex flex-wrap gap-5 text-sm">
            <a className="linkish !no-underline hover:!underline" href="#/docs">Docs</a>
            <a className="linkish !no-underline hover:!underline" href={REPO} target="_blank" rel="noreferrer">GitHub</a>
            <a className="linkish !no-underline hover:!underline" href={`${REPO}/blob/main/docs/REPORT.md`} target="_blank" rel="noreferrer">Report</a>
          </nav>
          <span className="micro">OpenCV 5 · AWS Graviton4 · Amazon Bedrock Nova</span>
        </footer>
      </div>
    </div>
  );
}
