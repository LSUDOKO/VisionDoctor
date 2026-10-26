import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, post, type CameraDetail as Detail, type HistoryRow } from "../api";
import {
  ACC_HINT, CHECKS, Card, Empty, ErrorNote, Gauge, Icon, SeverityBar, Skeleton, StatusTag, Tag, Tip,
  ago, bust, clock, errText, human, ms, pct, tooltipStyle, useChartColors, useFeedback,
} from "../ui";

function BeforeAfter({ d, heat }: { d: Detail; heat: boolean }) {
  const [pos, setPos] = useState(50);
  const ts = d.latest_report?.ts ?? d.last_scan_at;
  const worst = Object.entries(d.latest_report?.checks ?? {}).sort((a, b) => b[1].severity - a[1].severity)[0];
  const desc = worst && worst[1].severity > 0 ? `, ${worst[0]} severity ${worst[1].severity}` : ", no fault detected";
  const current = bust(heat && d.images.heatmap ? d.images.heatmap : d.images.current, ts);
  const reference = d.images.reference;
  if (!reference || !current) return <Empty icon="scan" title="No images yet">Run a scan to capture the reference and current view.</Empty>;
  return (
    <div className="ba">
      <img src={current} alt={`${d.camera_id} ${heat ? "fault heat-map" : "current view"}${desc}`} />
      <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}>
        <img src={reference} alt={`${d.camera_id} reference view (known-good baseline)`} />
      </div>
      <span className="imgtag left-2.5">Reference</span>
      <span className="imgtag right-2.5">{heat ? "Heat map" : "Current"}</span>
      <div className="ba-line" style={{ left: `calc(${pos}% - 1px)` }} />
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(+e.target.value)}
        aria-label="Before/after slider: left shows more of the current view, right shows more of the reference" />
      <div className="ba-knob" style={{ left: `${pos}%` }}><Icon name="back" size={12} /><Icon name="back" size={12} className="-ml-1 rotate-180" /></div>
    </div>
  );
}

function History({ id }: { id: string }) {
  const c = useChartColors();
  const q = useQuery({ queryKey: ["history", id], queryFn: () => api<HistoryRow[]>(`/api/cameras/${id}/history`), refetchInterval: 15000 });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <Skeleton className="h-64 w-full" />;
  const rows = q.data.map((r) => ({ ts: r.ts, overall: r.overall, acc: r.predicted_ai_accuracy }));
  if (!rows.length) return <Empty icon="scan" title="No scans in the last 24 hours" />;
  return (
    <div className="h-64" role="img" aria-label={`24-hour history for ${id}: ${rows.length} scans. Latest image health ${pct(rows.at(-1)!.overall)}, predicted accuracy ${pct(rows.at(-1)!.acc)}.`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 24, bottom: 0, left: -12 }}>
          <CartesianGrid stroke={c.line} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="ts" type="number" domain={["dataMin", "dataMax"]} tickFormatter={clock} stroke={c.label} fontSize={11} tickLine={false} axisLine={{ stroke: c.line }} fontFamily="Roboto Mono, monospace" />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} stroke={c.label} fontSize={11} tickLine={false} axisLine={false} fontFamily="Roboto Mono, monospace" />
          <Tooltip labelFormatter={(v) => new Date(Number(v) * 1000).toLocaleString()} formatter={(v) => pct(Number(v), 1)} contentStyle={tooltipStyle(c)} />
          <Legend wrapperStyle={{ fontSize: 12, color: c.ink }} iconType="plainline" />
          <Line type="monotone" dataKey="overall" name="Image health" stroke={c.ink} dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line type="monotone" dataKey="acc" name="Predicted accuracy" stroke={c.terracotta} dot={false} strokeWidth={2} strokeDasharray="5 3" isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function CameraDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { toast, confirm } = useFeedback();
  const [heat, setHeat] = useState(false);
  const q = useQuery({ queryKey: ["camera", id], queryFn: () => api<Detail>(`/api/cameras/${id}`), refetchInterval: 3000 });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["camera", id] }); qc.invalidateQueries({ queryKey: ["history", id] }); };
  const scan = useMutation({
    mutationFn: () => post(`/api/cameras/${id}/scan`),
    onSuccess: () => { refresh(); toast({ title: "Scan complete", body: `${id} re-scanned with all 11 checks.` }); },
    onError: (e) => toast({ title: "Scan failed", body: errText(e), error: true }),
  });
  const rollback = useMutation({
    mutationFn: (repair_id: string) => post(`/api/cameras/${id}/rollback`, { repair_id }),
    onSuccess: () => { refresh(); toast({ title: "Correction rolled back" }); },
    onError: (e) => toast({ title: "Rollback failed", body: errText(e), error: true }),
  });

  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return (
    <div className="space-y-6" aria-busy="true"><Skeleton className="h-4 w-24" /><Skeleton className="h-28 w-full" />
      <div className="grid gap-6 lg:grid-cols-2"><Skeleton className="aspect-video" /><Skeleton className="aspect-video" /></div></div>
  );
  const d = q.data;
  const r = d.latest_report;
  const acc = r?.predicted_ai_accuracy ?? d.predicted_ai_accuracy;
  const checks = Object.entries(r?.checks ?? {}).sort((a, b) => b[1].severity - a[1].severity || a[0].localeCompare(b[0]));
  const doRollback = async (repair_id: string, type: string) => {
    if (await confirm({ title: `Roll back ${human(type)}?`, danger: true, confirm: "Roll back",
      body: <>The camera returns to its raw feed for this correction. The next scan may open a new incident if the fault is still there.</> }))
      rollback.mutate(repair_id);
  };

  return (
    <div className="space-y-6">
      <a href="#/fleet" className="btn ghost sm -ml-2"><Icon name="back" /> Fleet</a>

      <section className="card grid gap-6 p-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-end lg:p-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusTag status={d.status} />
            <Tag mono tone="line">{d.camera_id}</Tag>
            <Tag mono tone="line">{d.site}</Tag>
            <Tag mono tone="line" title="How important this camera is, 1 (low) to 5 (critical)">criticality {d.criticality}/5</Tag>
          </div>
          <h1 className="display mt-4 text-[clamp(28px,4vw,40px)] leading-tight">{d.name}</h1>
          <div className="mt-6 flex flex-wrap items-end gap-x-10 gap-y-4">
            <div>
              <div className="flex items-center gap-1.5"><span className="micro">Predicted accuracy</span><Tip text={ACC_HINT} /></div>
              <div className="big-num mt-2 text-[clamp(52px,7vw,76px)]" data-testid="camera-accuracy">{pct(acc, 1)}</div>
            </div>
            <div className="grid grid-cols-2 gap-8 pb-1">
              <div><div className="micro">Image health</div><div className="big-num mt-1.5 text-[26px]">{pct(r?.overall_score ?? d.overall_score)}</div></div>
              <div><div className="micro">Scan time</div><div className="big-num mt-1.5 text-[26px]">{ms(r?.scan_ms)}</div></div>
            </div>
          </div>
          <div className="mt-5 max-w-xl"><Gauge value={acc} label="Predicted accuracy" /></div>
        </div>
        <div className="flex flex-col items-start gap-2 md:items-end">
          <button className="btn primary" onClick={() => scan.mutate()} disabled={scan.isPending}>
            <Icon name="refresh" className={scan.isPending ? "spin" : ""} />{scan.isPending ? "Scanning…" : "Scan now"}
          </button>
          <span className="text-xs muted">Last scan {ago(r?.ts ?? d.last_scan_at)}</span>
        </div>
      </section>

      {d.open_incident && (
        <a href="#/incidents" className="flex flex-wrap items-center gap-3 rounded-card px-5 py-4 no-underline" style={{ background: "var(--danger-tint)" }}>
          <Icon name="alert" className="text-danger" />
          <span className="font-semibold text-danger">Open incident</span>
          <span className="mono text-xs text-ink">{d.open_incident.incident_id}</span>
          <span className="text-sm text-ink">{(d.open_incident.fault_types ?? []).map((f) => CHECKS[f]?.label ?? human(f)).join(", ")} · {human(d.open_incident.state)}</span>
          <span className="ml-auto text-sm font-medium text-ink">Go to queue →</span>
        </a>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Card title="Reference vs current" hint="Drag the slider to compare the known-good reference with what the camera sees now. The heat map shows where faults were found."
          right={<div className="seg" role="group" aria-label="Image layer">
            <button aria-pressed={!heat} onClick={() => setHeat(false)}>Image</button>
            <button aria-pressed={heat} onClick={() => setHeat(true)} disabled={!d.images.heatmap}>Heat map</button>
          </div>}>
          <BeforeAfter d={d} heat={heat} />
          {d.active_sim_faults.length > 0 && (
            <p className="mt-3 flex flex-wrap items-center gap-1.5 text-xs muted">
              <span>Simulator ground truth (hidden from the scanner):</span>
              {d.active_sim_faults.map((f, i) => <Tag key={i} tone="blush" mono>{f.fault} · sev {f.severity}</Tag>)}
            </p>
          )}
        </Card>
        <Card title="Health checks" right={<span className="micro">severity 0–5</span>}>
          {checks.length ? <div className="divide-y divide-[var(--hairline-soft)]">{checks.map(([n, c]) => <SeverityBar key={n} name={n} severity={c.severity} score={c.score} />)}</div>
            : <Empty icon="scan" title="No report yet" />}
        </Card>
      </div>

      <Card title="Last 24 hours" hint="Image health is the overall check score; predicted accuracy is the label-free estimate for the detector on this camera.">
        <History id={id} />
      </Card>

      <Card title="Active corrections" hint="Bounded software repairs currently applied to this camera's feed. Each was verified by a re-scan.">
        {d.corrections.length === 0 ? <p className="text-sm muted">No software corrections active. The raw feed is going to the detector.</p> : (
          <ul className="divide-y divide-[var(--hairline-soft)]">
            {d.corrections.map((c) => (
              <li key={c.repair_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="grid h-9 w-9 flex-none place-items-center rounded-[8px] bg-mint text-forest"><Icon name="wrench" /></span>
                  <div className="min-w-0">
                    <div className="font-semibold text-ink">{human(c.type)}</div>
                    <div className="mono truncate text-[11px] muted" title={JSON.stringify(c.params)}>{c.repair_id} · {JSON.stringify(c.params ?? {})}</div>
                  </div>
                </div>
                <button className="btn danger sm" disabled={rollback.isPending} onClick={() => doRollback(c.repair_id, c.type)}
                  aria-label={`Roll back ${c.type} correction ${c.repair_id}`}>Rollback</button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
