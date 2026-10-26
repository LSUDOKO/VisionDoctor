import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, tokenKey } from "./api";
import CameraDetail from "./screens/CameraDetail";
import Demo from "./screens/Demo";
import Fleet from "./screens/Fleet";
import Incidents from "./screens/Incidents";
import Performance from "./screens/Performance";
import Traces from "./screens/Traces";

const TABS = [
  { id: "fleet", label: "Fleet" },
  { id: "incidents", label: "Incidents" },
  { id: "traces", label: "Traces" },
  { id: "perf", label: "Performance" },
  { id: "demo", label: "Demo control" },
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
  const [theme, setTheme] = useState(() => localStorage.getItem("vd_theme") ?? "dark");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("vd_theme", theme);
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")] as const;
}

interface AuthConfig { auth: boolean; region: string; client_id: string | null }

async function cognitoSignIn(cfg: AuthConfig, username: string, password: string): Promise<string> {
  const res = await fetch(`https://cognito-idp.${cfg.region}.amazonaws.com/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth" },
    body: JSON.stringify({ AuthFlow: "USER_PASSWORD_AUTH", ClientId: cfg.client_id, AuthParameters: { USERNAME: username, PASSWORD: password } }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message ?? "Sign-in failed");
  if (!data.AuthenticationResult) throw new Error(`Additional step required: ${data.ChallengeName ?? "unknown"}`);
  return data.AuthenticationResult.AccessToken as string;
}

function Settings({ onClose, cfg }: { onClose: () => void; cfg?: AuthConfig }) {
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const signedIn = !!localStorage.getItem(tokenKey);
  const signOut = () => { localStorage.removeItem(tokenKey); window.location.reload(); };
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cfg?.client_id) return;
    setBusy(true); setErr(null);
    try {
      localStorage.setItem(tokenKey, await cognitoSignIn(cfg, user.trim(), pass));
      window.location.reload();
    } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="panel absolute right-0 top-12 z-20 w-[min(22rem,calc(100vw-2rem))] p-4 shadow-xl" role="dialog" aria-label="Sign in">
      <h2 className="label mb-2">{signedIn ? "Account" : "Sign in"}</h2>
      {!cfg?.auth ? (
        <p className="mb-3 text-xs text-muted">This deployment runs without authentication (local demo).</p>
      ) : signedIn ? (
        <p className="mb-3 text-xs text-muted">Signed in with Amazon Cognito.</p>
      ) : (
        <form onSubmit={submit} className="space-y-2">
          <label className="block text-xs" htmlFor="vd-user">Email</label>
          <input id="vd-user" className="field w-full" type="email" autoComplete="username" value={user} onChange={(e) => setUser(e.target.value)} required />
          <label className="block text-xs" htmlFor="vd-pass">Password</label>
          <input id="vd-pass" className="field w-full" type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} required />
          {err && <p role="alert" className="text-xs text-bad">{err}</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" className="btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          </div>
        </form>
      )}
      {(signedIn || !cfg?.auth) && (
        <div className="mt-3 flex justify-end gap-2">
          {signedIn && <button className="btn" onClick={signOut}>Sign out</button>}
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      )}
    </div>
  );
}

export default function App() {
  const parts = useHash();
  const [theme, toggleTheme] = useTheme();
  const [settings, setSettings] = useState(false);
  const config = useQuery({ queryKey: ["config"], queryFn: () => api<AuthConfig>("/api/config"), staleTime: Infinity });
  const needsLogin = !!config.data?.auth && !localStorage.getItem(tokenKey);
  useEffect(() => { if (needsLogin) setSettings(true); }, [needsLogin]);
  const health = useQuery({ queryKey: ["health"], queryFn: () => api<{ status: string; opencv: string; agent: string; backend: string }>("/health"), refetchInterval: 15000 });
  const [tab, id] = parts;
  const active = tab === "camera" ? "fleet" : (TABS.find((t) => t.id === tab)?.id ?? "fleet");
  const h = health.data;

  return (
    <div className="mx-auto min-h-screen max-w-[1440px] px-4 pb-16 sm:px-6">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 btn">Skip to content</a>
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-line py-4">
        <div className="flex items-center gap-3">
          <svg aria-hidden width="34" height="34" viewBox="0 0 32 32" className="text-accent">
            <circle cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="2.5" />
            <circle cx="16" cy="16" r="5" fill="currentColor" />
            <path d="M3 16h5M24 16h5" stroke="currentColor" strokeWidth="2" />
          </svg>
          <div>
            <h1 className="text-lg font-bold leading-tight tracking-tight">VisionDoctor</h1>
            <p className="text-xs text-muted">The AI that watches the cameras</p>
          </div>
        </div>
        <nav role="tablist" aria-label="Sections" className="no-scrollbar order-3 -mx-1 flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {TABS.map((t) => (
            <a key={t.id} role="tab" aria-selected={active === t.id} href={`#/${t.id}`}
              className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ${active === t.id ? "bg-accent/15 text-accent" : "text-muted hover:text-fg"}`}>
              {t.label}
            </a>
          ))}
        </nav>
        <div className="relative ml-auto flex items-center gap-2">
          <span className="hidden items-center gap-1.5 font-mono text-xs text-muted lg:flex"
            title={h ? `API ${h.status}; OpenCV ${h.opencv}; agent ${h.agent}; storage ${h.backend}` : "API unreachable"}>
            <span aria-hidden className={`h-2 w-2 rounded-full ${h?.status === "ok" ? "bg-ok" : "bg-crit"}`} />
            {h ? `API ${h.status} · OpenCV ${h.opencv} · ${h.agent}` : "API offline"}
          </span>
          <button className="btn" onClick={toggleTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            <span aria-hidden>{theme === "dark" ? "☀" : "☾"}</span>
          </button>
          <button className="btn" onClick={() => setSettings(!settings)} aria-expanded={settings}>
            {localStorage.getItem(tokenKey) ? "Signed in" : "Sign in"}
          </button>
          {settings && <Settings cfg={config.data} onClose={() => setSettings(false)} />}
        </div>
      </header>
      <main id="main" className="pt-6">
        {tab === "camera" && id ? <CameraDetail id={id} />
          : active === "incidents" ? <Incidents />
          : active === "traces" ? <Traces id={id} />
          : active === "perf" ? <Performance />
          : active === "demo" ? <Demo />
          : <Fleet />}
      </main>
    </div>
  );
}
