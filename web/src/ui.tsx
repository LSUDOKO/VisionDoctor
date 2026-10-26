import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Status } from "./api";

/* ---------- icons: one stroke family, 16px grid ---------- */
const PATHS = {
  check: "M3.5 8.5l3 3 6-7",
  x: "M4 4l8 8M12 4l-8 8",
  eye: "M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8s-2.4 4.5-6.5 4.5S1.5 8 1.5 8zM8 10a2 2 0 100-4 2 2 0 000 4z",
  alert: "M8 1.8l6.5 11.7H1.5zM8 6.2v3.4M8 11.6v.1",
  half: "M8 1.8a6.2 6.2 0 100 12.4A6.2 6.2 0 008 1.8zM8 1.8v12.4",
  refresh: "M13.5 7.5A5.5 5.5 0 103 10.2M13.8 3v4.5H9.3",
  sun: "M8 11a3 3 0 100-6 3 3 0 000 6zM8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1",
  moon: "M13.5 9.5A6 6 0 016.5 2.5a6 6 0 107 7z",
  menu: "M2.5 4.5h11M2.5 8h11M2.5 11.5h11",
  chev: "M4 6l4 4 4-4",
  back: "M10 3.5L5.5 8l4.5 4.5",
  play: "M5 3.2v9.6L12.6 8z",
  user: "M8 8a3 3 0 100-6 3 3 0 000 6zM2.5 14.5c.6-2.8 2.8-4.4 5.5-4.4s4.9 1.6 5.5 4.4",
  bolt: "M9 1.5L3.5 9h4l-1 5.5L12 7H8z",
  shield: "M8 1.5l5.5 2v4.2c0 3.3-2.3 5.9-5.5 6.8-3.2-.9-5.5-3.5-5.5-6.8V3.5z",
  wrench: "M10.5 2a3.5 3.5 0 00-3.3 4.6L2.3 11.5a1.3 1.3 0 001.9 1.9l4.9-4.9A3.5 3.5 0 0014 5.2l-2 2-2-.5-.5-2z",
  dash: "M3.5 8h9",
  scan: "M2 5V2.5h2.5M11.5 2.5H14V5M14 11v2.5h-2.5M4.5 13.5H2V11M2 8h12",
  github: "M8 1.5a6.5 6.5 0 00-2 12.7c.3 0 .4-.2.4-.3v-1.2c-1.8.4-2.2-.8-2.2-.8-.3-.7-.7-.9-.7-.9-.6-.4 0-.4 0-.4.6 0 1 .7 1 .7.6 1 1.5.7 1.9.5 0-.4.2-.7.4-.9-1.4-.2-3-.7-3-3.2 0-.7.3-1.3.7-1.8-.1-.2-.3-.8 0-1.7 0 0 .6-.2 1.8.7a6 6 0 013.2 0c1.2-.9 1.8-.7 1.8-.7.3.9.1 1.5 0 1.7.4.5.7 1.1.7 1.8 0 2.5-1.6 3-3 3.2.2.2.4.6.4 1.2v1.8c0 .1.1.4.4.3A6.5 6.5 0 008 1.5z",
} as const;
export type IconName = keyof typeof PATHS;
export function Icon({ name, size = 16, className = "" }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d={PATHS[name]} />
    </svg>
  );
}

/* ---------- the logo: a yellow tile carrying a hand-drawn "vd" ---------- */
export function Logo({ href = "#/", size = 34, word = true }: { href?: string; size?: number; word?: boolean }) {
  return (
    <a className="logo" href={href} aria-label="VisionDoctor home">
      <span className="lgmark" style={{ width: size, height: size }} aria-hidden>
        <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9.5 14.5c1.4 3.9 2.9 7.6 4.6 11.3 1.5-3.8 2.9-7.5 4.4-11.3" />
          <path d="M31 9.5c.3 5.6.2 11.1 0 16.6M31 19.6c-1.6-3-7.4-2.6-7.7 2-.3 4.6 5.4 6.2 7.7 2.6" />
        </svg>
      </span>
      {word && <span className="lgword">VisionDoctor</span>}
    </a>
  );
}

/* ---------- status: icon + text, never colour alone ---------- */
export const STATUS: Record<Status, { icon: IconName; label: string; cls: string; hint: string }> = {
  healthy: { icon: "check", label: "Healthy", cls: "mint", hint: "All image-quality checks pass." },
  watch: { icon: "eye", label: "Watch", cls: "warn", hint: "A minor issue was seen; being watched, no action yet." },
  degraded: { icon: "alert", label: "Degraded", cls: "danger", hint: "Image quality is hurting the detection AI." },
  failed: { icon: "x", label: "Failed", cls: "failed", hint: "The camera is unusable (dead, frozen or blocked)." },
  repairing: { icon: "refresh", label: "Repairing", cls: "teal", hint: "An automatic correction is being applied and verified." },
};
export function StatusTag({ status, sm = false }: { status: Status; sm?: boolean }) {
  const s = STATUS[status] ?? STATUS.watch;
  return (
    <span className={`tag ${s.cls}${sm ? " sm" : ""}`} title={s.hint}>
      <Icon name={s.icon} size={sm ? 11 : 12} className={status === "repairing" ? "spin" : ""} />
      {s.label}
    </span>
  );
}

export function Tag({ children, tone = "", mono = false, title }: { children: ReactNode; tone?: string; mono?: boolean; title?: string }) {
  return <span title={title} className={`tag ${tone}${mono ? " mono" : ""}`}>{children}</span>;
}

/* ---------- the 11 checks, in plain language ---------- */
export const CHECKS: Record<string, { label: string; what: string; repair?: string }> = {
  freeze: { label: "Freeze", what: "The picture stopped changing, or the frame is dead or uniform." },
  glare: { label: "Glare", what: "Bright light (sun, headlights, IR bounce) is washing out part of the view." },
  occlusion: { label: "Occlusion", what: "Something is physically blocking part of the lens: a sign, a branch, a hand." },
  exposure: { label: "Exposure", what: "The image is too dark or too bright overall.", repair: "exposure" },
  color_cast: { label: "Colour cast", what: "Colours are tinted, e.g. a stuck IR-cut filter or a white-balance error.", repair: "white balance" },
  noise: { label: "Noise", what: "Grain or static, often from low light or high sensor gain.", repair: "denoise" },
  haze: { label: "Haze", what: "Contrast is lost to fog, condensation or a dirty dome.", repair: "dehaze" },
  drift: { label: "Drift", what: "The camera has rotated or shifted away from its reference view.", repair: "realign" },
  sharpness: { label: "Sharpness", what: "The image is out of focus or defocused." },
  vibration: { label: "Vibration", what: "The camera is shaking, causing motion blur between frames." },
  smudge: { label: "Smudge", what: "Dirt, rain drops or a spider web on the lens soften part of the view." },
};

/* ---------- formatting ---------- */
export const ACC_HINT = "Predicted accuracy: how well the detection AI on this camera is likely working right now, estimated without labels.";
export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(digits)}%`;
export const ms = (v: number | null | undefined) =>
  v === null || v === undefined ? "—" : v >= 1000 ? `${(v / 1000).toFixed(2)} s` : `${v.toFixed(v < 10 ? 2 : 0)} ms`;
export function ago(ts?: number | null): string {
  if (!ts) return "never";
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 60) return `${Math.round(s)} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
export const clock = (ts: number) => new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const human = (s: string) => s.replace(/_/g, " ");
export const go = (path: string) => { window.location.hash = `#/${path}`; };
/** Cache-bust a refreshed image. Presigned S3 URLs already carry a query string and break if altered: leave them alone. */
export const bust = (url: string | undefined, ts?: number | null) =>
  !url ? undefined : url.includes("?") ? url : `${url}?t=${Math.floor(ts ?? 0)}`;

/* ---------- small building blocks ---------- */
export function Stat({ label, value, hint, sub }: { label: string; value: ReactNode; hint?: string; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5">
        <span className="micro truncate">{label}</span>
        {hint && <Tip text={hint} />}
      </div>
      <div className="big-num mt-2 text-[30px]">{value}</div>
      {sub && <div className="mt-1 text-xs muted">{sub}</div>}
    </div>
  );
}

export function Card({ title, right, children, className = "", hint }: { title?: string; right?: ReactNode; children: ReactNode; className?: string; hint?: string }) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || right) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">{title && <h2 className="h-card">{title}</h2>}{hint && <Tip text={hint} />}</div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export const Skeleton = ({ className = "" }: { className?: string }) => <div aria-hidden className={`skel ${className}`} />;

export function Empty({ icon = "check", title, children }: { icon?: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="card tint flex flex-col items-center px-6 py-12 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-[10px] bg-yellow text-forest"><Icon name={icon} size={20} /></span>
      <p className="mt-4 text-base font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm muted">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p role="alert" className="flex items-start gap-2 rounded-card border border-danger px-3 py-2.5 text-sm text-danger" style={{ background: "var(--danger-tint)" }}>
      <Icon name="alert" className="mt-0.5 flex-none" />
      {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

/** Keyboard-reachable tooltip: a focusable trigger plus an aria-describedby popup. */
export function Tip({ text, align = "", label = "More info" }: { text: string; align?: "" | "end" | "start"; label?: string }) {
  const id = useId();
  return (
    <span className={`tip ${align}`}>
      <button type="button" aria-label={label} aria-describedby={id}>?</button>
      <span role="tooltip" id={id}>{text}</span>
    </span>
  );
}

export function SeverityBar({ name, severity, score }: { name: string; severity: number; score: number }) {
  const info = CHECKS[name];
  return (
    <div className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)_3.2rem] items-center gap-3 py-1.5">
      <span className="flex min-w-0 items-center gap-1.5">
        <span className="truncate text-sm font-medium text-ink">{info?.label ?? human(name)}</span>
        {info && <Tip text={`${info.what}${info.repair ? ` Software can fix this (${info.repair}).` : " Needs a person if severe."}`} align="start" label={`About ${info.label}`} />}
      </span>
      <div className={`sev s${severity}`} role="meter" aria-label={`${info?.label ?? name} severity`} aria-valuemin={0} aria-valuemax={5} aria-valuenow={severity}
        aria-valuetext={`severity ${severity} of 5, score ${score.toFixed(2)}`}>
        {[1, 2, 3, 4, 5].map((n) => <i key={n} className={n <= severity ? "on" : ""} />)}
      </div>
      <span className={`mono text-right text-xs ${severity >= 3 ? "text-danger" : "muted"}`}>{severity === 0 ? "ok" : `sev ${severity}`}</span>
    </div>
  );
}

export function PillSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[];
}) {
  return (
    <span className="pillsel">
      <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <Icon name="chev" size={12} />
    </span>
  );
}

export function Gauge({ value, label, sm = false }: { value: number | null | undefined; label: string; sm?: boolean }) {
  const v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className={`gauge${sm ? " sm" : ""}`} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)}>
      <i style={{ width: `${v * 100}%` }} />
    </div>
  );
}

/* ---------- chart colours read from the live theme (SVG attributes can't resolve var()) ---------- */
export function useChartColors() {
  const read = () => {
    const s = getComputedStyle(document.documentElement);
    const g = (n: string) => s.getPropertyValue(n).trim();
    return { ink: g("--ink"), label: g("--label"), line: g("--hairline"), page: g("--page"), danger: g("--danger"), terracotta: g("--terracotta"), yellow: g("--yellow"), teal: g("--teal-ink") };
  };
  const [c, setC] = useState(read);
  useEffect(() => {
    const mo = new MutationObserver(() => setC(read()));
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => mo.disconnect();
  }, []);
  return c;
}
export const tooltipStyle = (c: ReturnType<typeof useChartColors>) => ({
  background: c.page, border: `1px solid ${c.line}`, borderRadius: 8, color: c.ink, fontSize: 12, fontFamily: "Inter, sans-serif",
});

/* ---------- feedback: toasts + promise-based confirm, one provider ---------- */
interface ToastMsg { id: number; title: string; body?: string; error?: boolean }
interface ConfirmOpts { title: string; body?: ReactNode; confirm: string; danger?: boolean }
interface Feedback { toast: (t: Omit<ToastMsg, "id">) => void; confirm: (o: ConfirmOpts) => Promise<boolean> }
const Ctx = createContext<Feedback>({ toast: () => {}, confirm: async () => false });
export const useFeedback = () => useContext(Ctx);

export function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMsg[]>([]);
  const [ask, setAsk] = useState<(ConfirmOpts & { resolve: (v: boolean) => void }) | null>(null);
  const dlg = useRef<HTMLDialogElement>(null);
  const toast = useCallback((t: Omit<ToastMsg, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((xs) => [...xs.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((xs) => xs.filter((x) => x.id !== id)), t.error ? 8000 : 4500);
  }, []);
  const confirm = useCallback((o: ConfirmOpts) => new Promise<boolean>((resolve) => setAsk({ ...o, resolve })), []);
  useEffect(() => { if (ask && dlg.current && !dlg.current.open) dlg.current.showModal(); }, [ask]);
  const close = (v: boolean) => { ask?.resolve(v); dlg.current?.close(); setAsk(null); };

  return (
    <Ctx.Provider value={{ toast, confirm }}>
      {children}
      <dialog ref={dlg} className="confirm" onCancel={(e) => { e.preventDefault(); close(false); }}
        onClick={(e) => { if (e.target === dlg.current) close(false); }} aria-labelledby="confirm-title">
        {ask && (
          <div>
            <h2 id="confirm-title">{ask.title}</h2>
            {ask.body && <div className="mt-2 text-sm leading-relaxed text-body">{ask.body}</div>}
            <div className="mt-6 flex justify-end gap-2">
              <button className="btn" onClick={() => close(false)} autoFocus>Cancel</button>
              <button className={`btn ${ask.danger ? "danger solid" : "primary"}`} onClick={() => close(true)}>{ask.confirm}</button>
            </div>
          </div>
        )}
      </dialog>
      <div className="toasts" aria-live="polite" role="status">
        {toasts.map((t) => (
          <div key={t.id} className={`toast${t.error ? " error" : ""}`}>
            <span className="ti"><Icon name={t.error ? "alert" : "check"} size={13} /></span>
            <div className="min-w-0"><b>{t.title}</b>{t.body && <span className="tm">{t.body}</span>}</div>
            <button aria-label="Dismiss" onClick={() => setToasts((xs) => xs.filter((x) => x.id !== t.id))}>×</button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

export type Theme = "light" | "dark";
export function ThemeToggle({ theme, toggle }: { theme: Theme; toggle: () => void }) {
  return (
    <button className="btn ghost sm icon" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} title="Toggle theme">
      <Icon name={theme === "dark" ? "sun" : "moon"} />
    </button>
  );
}

