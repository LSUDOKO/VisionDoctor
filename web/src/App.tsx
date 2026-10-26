import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, tokenKey, type Incident } from "./api";
import CameraDetail from "./screens/CameraDetail";
import Demo from "./screens/Demo";
import Docs from "./screens/Docs";
import Fleet from "./screens/Fleet";
import Incidents from "./screens/Incidents";
import Landing from "./screens/Landing";
import Performance from "./screens/Performance";
import Traces from "./screens/Traces";
import { ErrorNote, Icon, Logo, Skeleton, ThemeToggle, go, type Theme } from "./ui";

const TABS = [
  { id: "fleet", label: "Fleet" },
  { id: "incidents", label: "Incidents" },
  { id: "traces", label: "Traces" },
  { id: "perf", label: "Performance" },
  { id: "demo", label: "Demo" },
  { id: "docs", label: "Docs" },
] as const;

function useHash(): string[] {
  const read = () => window.location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  const [parts, setParts] = useState(read);
  useEffect(() => {
    const on = () => { setParts(read()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return parts;
}

function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => (localStorage.getItem("vd_theme") === "dark" ? "dark" : "light"));
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#142408" : "#fcfaf5");
    localStorage.setItem("vd_theme", theme);
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")] as const;
}

interface AuthConfig { auth: boolean; region: string; client_id: string | null }
interface Health { status: string; opencv: string; agent: string; backend: string; is_cool?: boolean }

async function cognitoSignIn(cfg: AuthConfig, username: string, password: string): Promise<string> {
  const res = await fetch(`https://cognito-idp.${cfg.region}.amazonaws.com/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth" },
    body: JSON.stringify({ AuthFlow: "USER_PASSWORD_AUTH", ClientId: cfg.client_id, AuthParameters: { USERNAME: username, PASSWORD: password } }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message ?? "Sign-in failed");
  if (!data.AuthenticationResult) throw new Error(`Additional step required: ${data.ChallengeName ?? "unknown"}`);
  return data.AuthenticationResult.IdToken as string; // ID token carries the email shown on approvals
}

/* ---------- full-page sign-in ---------- */
function Login({ cfg, theme, toggleTheme }: { cfg?: AuthConfig; theme: Theme; toggleTheme: () => void }) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (cfg && !cfg.auth) go("fleet"); }, [cfg]);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!cfg?.client_id) { setErr("Sign-in is not configured on this deployment."); return; }
    setBusy(true); setErr(null);
    try {
      localStorage.setItem(tokenKey, await cognitoSignIn(cfg, user.trim(), pass));
      window.location.reload();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <main className="stage" data-testid="login-screen">
      <div className="absolute left-6 top-6"><Logo /></div>
      <div className="absolute right-6 top-6 flex items-center gap-2">
        <ThemeToggle theme={theme} toggle={toggleTheme} />
        <a className="btn sm" href="#/about">About</a>
      </div>
      <section className="rise">
        <span className="badge"><Icon name="eye" size={13} /> Operator console</span>
        <h1 className="display mt-5 text-[clamp(40px,5.2vw,62px)] leading-none" style={{ letterSpacing: "0.04em" }}>
          Every camera, <span className="hl wash">checked</span> before the AI trusts it.
        </h1>
        <p className="mt-5 max-w-[500px] text-[17px] leading-relaxed text-ink">
          Sign in to see fleet health, approve technician dispatches and read every agent decision.
        </p>
        <form onSubmit={submit} className="mt-8 grid max-w-[420px] gap-3" aria-describedby={err ? "login-err" : undefined}>
          <label className="grid gap-1.5">
            <span className="micro">Email</span>
            <input className="field" type="email" autoComplete="username" value={user} onChange={(e) => setUser(e.target.value)} required
              placeholder="you@company.com" aria-invalid={!!err} />
          </label>
          <label className="grid gap-1.5">
            <span className="micro">Password</span>
            <input className="field" type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required aria-invalid={!!err} />
          </label>
          {err && <div id="login-err"><ErrorNote error={err} /></div>}
          <button type="submit" className="btn primary big mt-2" disabled={busy || !cfg} data-testid="login-submit">
            {busy ? <><Icon name="refresh" className="spin" /> Signing in…</> : <span className="arrow flex items-center gap-2">Sign in</span>}
          </button>
          <p className="text-xs muted">Amazon Cognito · your ID token stays in this browser.</p>
        </form>
      </section>
      <section aria-hidden className="relative mx-auto hidden w-full max-w-[440px] md:block">
        <div className="sticky-back" />
        <div className="card relative rotate-[2.5deg] p-5" style={{ borderColor: "var(--ink)" }}>
          <div className="flex items-center justify-between"><span className="micro">cam-07 · loading dock</span><span className="tag teal sm"><Icon name="refresh" size={11} /> Repairing</span></div>
          <div className="mt-4 space-y-2.5">
            {[["Drift", 4], ["Haze", 1], ["Sharpness", 0], ["Glare", 0]].map(([n, s]) => (
              <div key={n} className="grid grid-cols-[6rem_1fr] items-center gap-3">
                <span className="text-sm font-medium text-ink">{n}</span>
                <div className={`sev s${s}`}>{[1, 2, 3, 4, 5].map((i) => <i key={i} className={i <= (s as number) ? "on" : ""} />)}</div>
              </div>
            ))}
          </div>
          <div className="divider mt-4 pt-3 text-xs muted">realign applied → re-scan → verified</div>
        </div>
      </section>
    </main>
  );
}

/* ---------- console shell: the floating nav pill ---------- */
function Shell({ active, theme, toggleTheme, cfg, children }: {
  active: string; theme: Theme; toggleTheme: () => void; cfg?: AuthConfig; children: React.ReactNode;
}) {
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), refetchInterval: 15000 });
  const awaiting = useQuery({ queryKey: ["incidents", false], queryFn: () => api<Incident[]>("/api/incidents?state=open"), refetchInterval: 5000, enabled: active !== "docs" || !!localStorage.getItem(tokenKey) || cfg?.auth === false });
  const [menu, setMenu] = useState<"" | "nav" | "acct">("");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const off = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setMenu(""); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(""); };
    document.addEventListener("click", off); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("click", off); document.removeEventListener("keydown", esc); };
  }, []);
  useEffect(() => setMenu(""), [active]);
  const h = health.data;
  const st = health.error ? "bad" : h?.status === "ok" ? "ok" : "wait";
  const pending = awaiting.data?.filter((i) => i.state === "awaiting_approval").length ?? 0;
  const signedIn = !!localStorage.getItem(tokenKey);
  const signOut = () => { localStorage.removeItem(tokenKey); window.location.hash = "#/"; window.location.reload(); };
  const link = (t: (typeof TABS)[number], cls: string) => (
    <a key={t.id} href={`#/${t.id}`} className={`${cls}${active === t.id ? " on" : ""}`} aria-current={active === t.id ? "page" : undefined}>
      {t.label}
      {t.id === "incidents" && pending > 0 && <span className="badge" aria-label={`${pending} awaiting approval`}>{pending}</span>}
    </a>
  );

  return (
    <>
      <a href="#main" className="btn sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100]">Skip to content</a>
      <div className="navwrap" ref={ref}>
        <nav className="navpill relative" aria-label="Console">
          <Logo href="#/fleet" />
          <div className="navlinks hidden lg:flex">{TABS.map((t) => link(t, "navlink"))}</div>
          <div className="navright ml-auto lg:ml-0">
            <span className="apistat hidden xl:inline-flex" title={h ? `API ${h.status} · storage ${h.backend}` : "API unreachable"}>
              <span className={`dot ${st}`} aria-hidden />
              {health.error ? "API offline" : h ? (h.status === "ok" ? `OpenCV ${h.opencv}` : "API starting") : "connecting"}
            </span>
            {h && <span className="tag yellow mono hidden md:inline-flex" title="Which agent decides: Amazon Bedrock Nova or the deterministic policy">agent · {h.agent}</span>}
            <span className={`dot ${st} xl:hidden`} role="img" aria-label={`API ${st === "ok" ? "online" : st === "wait" ? "starting" : "offline"}`} />
            <ThemeToggle theme={theme} toggle={toggleTheme} />
            <button className="btn sm icon" aria-label="Account" aria-expanded={menu === "acct"} aria-haspopup="menu"
              onClick={(e) => { e.stopPropagation(); setMenu(menu === "acct" ? "" : "acct"); }}>
              <Icon name="user" />
            </button>
            <button className="btn sm lg:hidden" aria-label="Sections menu" aria-expanded={menu === "nav"} aria-haspopup="menu"
              onClick={(e) => { e.stopPropagation(); setMenu(menu === "nav" ? "" : "nav"); }}>
              <Icon name="menu" /> <span className="hidden sm:inline">{TABS.find((t) => t.id === active)?.label ?? "Menu"}</span>
            </button>
          </div>
          {menu === "nav" && (
            <div className="menu right-2 top-[calc(100%+8px)] lg:hidden" role="menu">
              {TABS.map((t) => link(t, "mi"))}
              {h && <div className="divider mt-1 flex flex-wrap items-center gap-2 px-2.5 pb-1 pt-2.5">
                <span className="apistat"><span className={`dot ${st}`} aria-hidden />OpenCV {h.opencv}</span>
                <span className="tag yellow mono">agent · {h.agent}</span>
              </div>}
            </div>
          )}
          {menu === "acct" && (
            <div className="menu right-2 top-[calc(100%+8px)]" role="menu">
              <div className="mhead">
                <div className="text-sm font-semibold text-ink">{signedIn ? "Signed in" : cfg?.auth ? "Not signed in" : "Local demo"}</div>
                <div className="text-xs muted">{signedIn ? "Amazon Cognito · operator" : cfg?.auth ? "Sign in to act on incidents" : "This deployment runs without authentication."}</div>
              </div>
              <a className="mi" href="#/about" role="menuitem"><Icon name="eye" /> About VisionDoctor</a>
              <a className="mi" href="https://github.com/LSUDOKO/VisionDoctor" target="_blank" rel="noreferrer" role="menuitem"><Icon name="github" /> GitHub</a>
              {signedIn ? <button className="mi danger" onClick={signOut} role="menuitem"><Icon name="back" /> Sign out</button>
                : cfg?.auth ? <a className="mi" href="#/login" role="menuitem"><Icon name="user" /> Sign in</a> : null}
            </div>
          )}
        </nav>
      </div>
      <main id="main" className="shell">{children}</main>
    </>
  );
}

function Boot() {
  return (
    <div className="grid min-h-dvh place-items-center" role="status" aria-label="Loading">
      <div className="flex flex-col items-center gap-4"><Logo word={false} size={44} /><Skeleton className="h-1.5 w-32" /></div>
    </div>
  );
}

export default function App() {
  const parts = useHash();
  const [theme, toggleTheme] = useTheme();
  const config = useQuery({ queryKey: ["config"], queryFn: () => api<AuthConfig>("/api/config"), staleTime: Infinity });
  const token = localStorage.getItem(tokenKey);
  const [tab = "", id] = parts;

  if (tab === "about" || (tab === "" && !token)) return <Landing theme={theme} toggleTheme={toggleTheme} signedIn={!!token} />;
  if (config.isLoading) return <Boot />;
  const needsLogin = !!config.data?.auth && !token;
  if (tab === "login" || (needsLogin && tab !== "docs")) return <Login cfg={config.data} theme={theme} toggleTheme={toggleTheme} />;

  const active = tab === "camera" ? "fleet" : (TABS.find((t) => t.id === tab)?.id ?? "fleet");
  return (
    <Shell active={active} theme={theme} toggleTheme={toggleTheme} cfg={config.data}>
      {config.error && <div className="mb-5"><ErrorNote error={`Backend unreachable: ${(config.error as Error).message}`} /></div>}
      {tab === "camera" && id ? <CameraDetail id={id} />
        : active === "incidents" ? <Incidents />
        : active === "traces" ? <Traces id={id} />
        : active === "perf" ? <Performance />
        : active === "demo" ? <Demo />
        : active === "docs" ? <Docs />
        : <Fleet />}
    </Shell>
  );
}
