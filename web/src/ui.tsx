import type { ReactNode } from "react";
import type { Status } from "./api";

export const STATUS: Record<Status, { icon: string; label: string; cls: string; hint: string }> = {
  healthy: { icon: "✓", label: "Healthy", cls: "text-ok border-ok/40 bg-ok/10", hint: "All image-quality checks pass." },
  watch: { icon: "◐", label: "Watch", cls: "text-warn border-warn/40 bg-warn/10", hint: "A minor issue was seen; being watched, no action yet." },
  degraded: { icon: "▲", label: "Degraded", cls: "text-bad border-bad/40 bg-bad/10", hint: "Image quality is hurting the detection AI." },
  failed: { icon: "✕", label: "Failed", cls: "text-crit border-crit/40 bg-crit/10", hint: "The camera is unusable (dead, frozen or blocked)." },
  repairing: { icon: "⟳", label: "Repairing", cls: "text-info border-info/40 bg-info/10", hint: "An automatic correction is being applied and verified." },
};

export function StatusChip({ status }: { status: Status }) {
  const s = STATUS[status] ?? STATUS.watch;
  return (
    <span title={s.hint} className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold ${s.cls}`}>
      <span aria-hidden className={status === "repairing" ? "spin" : ""}>{s.icon}</span>
      {s.label}
    </span>
  );
}

export const ACC_HINT =
  "Predicted accuracy: how well the detection AI on this camera is likely working right now, estimated without labels.";

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

export function Stat({ label, value, hint, tone = "" }: { label: string; value: ReactNode; hint: string; tone?: string }) {
  return (
    <div title={hint} className="min-w-0 px-4 py-3">
      <div className="label truncate">{label}</div>
      <div className={`num mt-1 text-2xl font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

const SEV = ["bg-ok", "bg-warn", "bg-warn", "bg-bad", "bg-crit", "bg-crit"];
export function SeverityBar({ name, severity, score }: { name: string; severity: number; score: number }) {
  return (
    <div className="grid grid-cols-[7.5rem_1fr_3.5rem] items-center gap-3 text-sm"
      title={`${name}: severity ${severity} of 5 (0 = fine). Check score ${score.toFixed(2)} (1.00 = perfect).`}>
      <span className="truncate font-mono text-xs">{name}</span>
      <div className="flex h-2.5 gap-0.5" role="meter" aria-label={`${name} severity`} aria-valuemin={0} aria-valuemax={5} aria-valuenow={severity}>
        {[1, 2, 3, 4, 5].map((n) => (
          <span key={n} className={`flex-1 rounded-sm ${n <= severity ? SEV[severity] : "bg-line/60"}`} />
        ))}
      </div>
      <span className="num text-right text-xs text-muted">sev {severity}</span>
    </div>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="p-6 text-sm text-muted" role="status">Loading {what}…</p>;
}

export function ErrorNote({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-md border border-crit/50 bg-crit/10 px-3 py-2 text-sm text-crit">
      {error instanceof Error ? error.message : String(error)}
    </p>
  );
}

export function Section({ title, children, right }: { title: string; children: ReactNode; right?: ReactNode }) {
  return (
    <section className="panel p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="label">{title}</h3>
        {right}
      </div>
      {children}
    </section>
  );
}

export const chartColors = { accent: "rgb(var(--accent))", ok: "rgb(var(--ok))", warn: "rgb(var(--warn))", muted: "rgb(var(--muted))", line: "rgb(var(--line))" };
export const go = (path: string) => { window.location.hash = `#/${path}`; };
