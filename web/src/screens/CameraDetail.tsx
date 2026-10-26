import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post, type CameraDetail as Detail, type HistoryRow } from "../api";
import { ACC_HINT, ErrorNote, Loading, Section, SeverityBar, StatusChip, ago, chartColors, clock, go, ms, pct } from "../ui";

function BeforeAfter({ d, heat }: { d: Detail; heat: boolean }) {
  const [pos, setPos] = useState(50);
  const worst = Object.entries(d.latest_report?.checks ?? {}).sort((a, b) => b[1].severity - a[1].severity)[0];
  const desc = worst && worst[1].severity > 0 ? `, ${worst[0]} severity ${worst[1].severity}` : ", no fault detected";
  const current = heat && d.images.heatmap ? d.images.heatmap : d.images.current;
  if (!d.images.reference || !current) return <p className="text-sm text-muted">No images yet; run a scan.</p>;
  return (
    <div>
      <div className="relative aspect-video select-none overflow-hidden rounded-md border border-line bg-raised">
        <img src={current} alt={`${d.camera_id} ${heat ? "fault heat-map" : "current view"}${desc}`} className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
          <img src={d.images.reference} alt={`${d.camera_id} reference view (known-good baseline)`} className="h-full w-full object-cover" />
        </div>
        <div aria-hidden className="pointer-events-none absolute inset-y-0 w-0.5 bg-accent" style={{ left: `${pos}%` }} />
        <span className="pointer-events-none absolute left-2 top-2 rounded bg-bg/80 px-1.5 py-0.5 text-xs font-semibold">Reference</span>
        <span className="pointer-events-none absolute right-2 top-2 rounded bg-bg/80 px-1.5 py-0.5 text-xs font-semibold">{heat ? "Heat-map" : "Current"}</span>
        <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(+e.target.value)} className="ba"
          aria-label="Before/after slider: drag left to see more of the current view, right to see more of the reference" />
      </div>
    </div>
  );
}

function History({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["history", id], queryFn: () => api<HistoryRow[]>(`/api/cameras/${id}/history`), refetchInterval: 15000 });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <Loading what="history" />;
  const rows = q.data.map((r) => ({ ts: r.ts, overall: r.overall, acc: r.predicted_ai_accuracy }));
  if (!rows.length) return <p className="text-sm text-muted">No scans in the last 24 h.</p>;
  return (
    <div className="h-64" role="img" aria-label={`24-hour history for ${id}: ${rows.length} scans. Latest overall health ${pct(rows.at(-1)!.overall)}, predicted AI accuracy ${pct(rows.at(-1)!.acc)}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
          <CartesianGrid stroke={chartColors.line} strokeDasharray="3 3" />
          <XAxis dataKey="ts" type="number" domain={["dataMin", "dataMax"]} tickFormatter={clock} stroke={chartColors.muted} fontSize={11} />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} stroke={chartColors.muted} fontSize={11} />
          <Tooltip labelFormatter={(v) => new Date(Number(v) * 1000).toLocaleString()} formatter={(v) => pct(Number(v), 1)}
            contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", color: "rgb(var(--fg))", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="overall" name="Overall image health" stroke={chartColors.accent} dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line type="monotone" dataKey="acc" name="Predicted AI accuracy" stroke={chartColors.warn} dot={false} strokeWidth={2} strokeDasharray="5 3" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function CameraDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const [heat, setHeat] = useState(false);
  const q = useQuery({ queryKey: ["camera", id], queryFn: () => api<Detail>(`/api/cameras/${id}`), refetchInterval: 3000 });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["camera", id] }); qc.invalidateQueries({ queryKey: ["history", id] }); };
  const scan = useMutation({ mutationFn: () => post(`/api/cameras/${id}/scan`), onSuccess: refresh });
  const rollback = useMutation({ mutationFn: (repair_id: string) => post(`/api/cameras/${id}/rollback`, { repair_id }), onSuccess: refresh });

  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <Loading what={id} />;
  const d = q.data;
  const r = d.latest_report;
  const checks = Object.entries(r?.checks ?? {}).sort((a, b) => b[1].severity - a[1].severity || a[0].localeCompare(b[0]));

  return (
    <div className="space-y-5">
      <button className="text-sm text-muted hover:text-accent" onClick={() => go("fleet")}>← Fleet</button>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h2 className="text-2xl font-semibold">{d.name}</h2>
        <StatusChip status={d.status} />
        <span className="font-mono text-xs text-muted">{d.camera_id} · {d.site} · criticality {d.criticality}/5</span>
        <div className="ml-auto flex gap-2">
          <button className="btn btn-primary" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <span aria-hidden className={scan.isPending ? "spin" : ""}>⟳</span>{scan.isPending ? "Scanning…" : "Scan now"}
          </button>
        </div>
      </div>
      {scan.error && <ErrorNote error={scan.error} />}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Section title="Reference vs current" right={
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={heat} onChange={(e) => setHeat(e.target.checked)} className="accent-[rgb(var(--accent))]" />
            Heat-map
          </label>}>
          <BeforeAfter d={d} heat={heat} />
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div title={ACC_HINT}><div className="label">Pred. AI accuracy</div><div className="num text-lg font-semibold">{pct(r?.predicted_ai_accuracy ?? d.predicted_ai_accuracy)}</div></div>
            <div title="Overall image health: 100% means every image-quality check passes."><div className="label">Image health</div><div className="num text-lg font-semibold">{pct(r?.overall_score ?? d.overall_score)}</div></div>
            <div title="How long the last full health scan took on the CPU."><div className="label">Scan time</div><div className="num text-lg font-semibold">{ms(r?.scan_ms)}</div></div>
          </div>
          <p className="mt-2 text-xs text-muted">Last scan {ago(r?.ts ?? d.last_scan_at)}.</p>
        </Section>

        <Section title="Health checks">
          {checks.length ? <div className="space-y-2">{checks.map(([n, c]) => <SeverityBar key={n} name={n} severity={c.severity} score={c.score} />)}</div>
            : <p className="text-sm text-muted">No report yet.</p>}
        </Section>
      </div>

      <Section title="Last 24 hours"><History id={id} /></Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Applied corrections">
          {d.corrections.length === 0 ? <p className="text-sm text-muted">No software corrections active.</p> : (
            <ul className="divide-y divide-line">
              {d.corrections.map((c) => (
                <li key={c.repair_id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <div className="font-mono text-sm font-semibold">{c.type}</div>
                    <div className="truncate font-mono text-[11px] text-muted" title={JSON.stringify(c.params)}>{c.repair_id} · {JSON.stringify(c.params ?? {})}</div>
                  </div>
                  <button className="btn btn-danger" disabled={rollback.isPending} onClick={() => rollback.mutate(c.repair_id)}
                    aria-label={`Roll back ${c.type} correction ${c.repair_id}`}>Rollback</button>
                </li>
              ))}
            </ul>
          )}
          {rollback.error && <ErrorNote error={rollback.error} />}
        </Section>
        <Section title="Incident & simulator">
          {d.open_incident ? (
            <a href="#/incidents" className="block rounded-md border border-bad/40 bg-bad/10 p-3 text-sm hover:border-bad">
              <span className="font-semibold text-bad">▲ Open incident</span> <span className="font-mono text-xs">{d.open_incident.incident_id}</span>
              <div className="text-xs text-muted">{(d.open_incident.fault_types ?? []).join(", ")} · {d.open_incident.state.replace(/_/g, " ")}</div>
            </a>
          ) : <p className="text-sm text-muted">No open incident.</p>}
          {d.active_sim_faults.length > 0 && (
            <p className="mt-3 font-mono text-xs text-muted" title="Faults injected by the demo simulator (ground truth, not visible to the scanner).">
              sim faults: {d.active_sim_faults.map((f) => `${f.fault} sev${f.severity}`).join(", ")}
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}
