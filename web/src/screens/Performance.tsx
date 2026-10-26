import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type OpMetrics } from "../api";
import { Card, Empty, ErrorNote, Skeleton, Tag, tooltipStyle, useChartColors } from "../ui";

interface BenchConfig {
  instance_type: string | null; is_cool?: boolean; cv2_version?: string; threads?: number;
  scans_per_min: number; scan_p50_ms: number; scan_p95_ms: number; usd_per_1M_scans: number | null;
}
interface Bench { available?: boolean; configs?: Record<string, BenchConfig>; ops?: { op: string; config: string; median_ms: number }[] }

const f = (v: number | null | undefined, d = 0) => (v == null ? "—" : v.toFixed(d));

function Bench() {
  const c = useChartColors();
  const q = useQuery({ queryKey: ["bench"], queryFn: () => api<Bench>("/api/bench") });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <div className="grid gap-5 md:grid-cols-2"><Skeleton className="h-56" /><Skeleton className="h-56" /></div>;
  if (q.data.available === false || !q.data.configs) return <Empty icon="bolt" title="No benchmark results yet">Run the bench script to measure scans per minute and cost per million scans.</Empty>;
  const configs = Object.entries(q.data.configs);
  const names = configs.map(([k]) => k);
  // ops table → one row per op, one numeric column per config
  const byOp = new Map<string, Record<string, number | string>>();
  const all = q.data.ops ?? [];
  const hd = all.some((o) => o.op.endsWith("@1080p")) ? all.filter((o) => o.op.endsWith("@1080p")) : all;
  for (const o of hd) {
    const row = byOp.get(o.op) ?? { op: o.op.replace("@1080p", "") };
    row[o.config] = o.median_ms;
    byOp.set(o.op, row);
  }
  const ops = [...byOp.values()].sort((a, b) => Number(b[names[0]] ?? 0) - Number(a[names[0]] ?? 0));
  const fills = [c.ink, c.terracotta, c.teal, c.label];

  return (
    <div className="space-y-6">
      <div className={`grid gap-5 ${configs.length > 1 ? "md:grid-cols-2" : ""}`}>
        {configs.map(([name, b], i) => (
          <section key={name} className={`note ${i === 0 ? "mint" : ""} !p-6`} aria-label={`Benchmark ${name}`}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="nk">{name}</span>
              <span className="ml-auto flex gap-1.5">
                {b.instance_type && <Tag tone="yellow" mono>{b.instance_type}</Tag>}
                <Tag tone="line" mono>{b.threads ?? "?"} threads · cv {b.cv2_version ?? "?"}</Tag>
              </span>
            </div>
            <div className="mt-5 flex items-baseline gap-2">
              <span className="big-num text-[64px]" style={{ color: "inherit" }}>{f(b.scans_per_min)}</span>
              <span className="text-sm font-medium">scans / min</span>
            </div>
            <dl className="mt-5 grid grid-cols-3 gap-3 border-t pt-4" style={{ borderColor: "currentColor", borderTopWidth: 1, opacity: 0.95 }}>
              <div><dt className="nk">p50</dt><dd className="big-num mt-1 text-xl" style={{ color: "inherit" }}>{f(b.scan_p50_ms)}<span className="text-xs"> ms</span></dd></div>
              <div><dt className="nk">p95</dt><dd className="big-num mt-1 text-xl" style={{ color: "inherit" }}>{f(b.scan_p95_ms)}<span className="text-xs"> ms</span></dd></div>
              <div><dt className="nk">per 1M scans</dt><dd className="big-num mt-1 text-xl" style={{ color: "inherit" }}>{b.usd_per_1M_scans == null ? "—" : `$${b.usd_per_1M_scans.toFixed(2)}`}</dd></div>
            </dl>
            <span className="nfoot">12 × 1080p cameras · full 11-check scan</span>
          </section>
        ))}
      </div>
      {ops.length > 0 && (
        <Card title="OpenCV op latency, 1080p" hint="Median time per core OpenCV operation in each benchmark configuration. Lower is faster.">
          <div className="h-80" role="img" aria-label={`Median op latency by configuration; slowest op is ${ops[0].op}`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ops} margin={{ top: 4, right: 8, bottom: 70, left: -8 }}>
                <CartesianGrid stroke={c.line} strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="op" stroke={c.label} fontSize={11} angle={-35} textAnchor="end" interval={0} tickLine={false} axisLine={{ stroke: c.line }} fontFamily="Roboto Mono, monospace" />
                <YAxis stroke={c.label} fontSize={11} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}`} unit=" ms" fontFamily="Roboto Mono, monospace" />
                <Tooltip contentStyle={tooltipStyle(c)} formatter={(v) => `${Number(v).toFixed(2)} ms`} cursor={{ fill: c.line, opacity: 0.4 }} />
                <Legend wrapperStyle={{ fontSize: 12, color: c.ink }} verticalAlign="top" align="right" iconType="square" />
                {names.map((n, i) => <Bar key={n} dataKey={n} fill={fills[i % fills.length]} radius={[3, 3, 0, 0]} isAnimationActive={false} />)}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  );
}

export default function Performance() {
  const ops = useQuery({ queryKey: ["ops"], queryFn: () => api<OpMetrics>("/api/metrics/ops"), refetchInterval: 5000 });
  const rows = Object.entries(ops.data ?? {}).map(([op, m]) => ({ op, ...m })).sort((a, b) => b.p50_ms - a.p50_ms);
  const max = Math.max(...rows.map((r) => r.p95_ms), 1);
  return (
    <div className="space-y-6">
      <div>
        <span className="micro">Console</span>
        <h1 className="h-page mt-1">Performance</h1>
        <p className="mt-2 max-w-2xl text-sm muted">Recorded benchmark runs (AWS Graviton4 vs a local x86 laptop) and live op timings from this server process.</p>
      </div>
      <Bench />
      <Card title="Live op latency" hint="Timings measured in this API process since it started. p50 = median; p95 = only 1 in 20 calls was slower."
        right={<span className="micro">this process</span>}>
        {ops.error && <ErrorNote error={ops.error} />}
        {!ops.data && !ops.error && <Skeleton className="h-40 w-full" />}
        {ops.data && rows.length === 0 && <p className="text-sm muted">No ops recorded yet. Timings appear after the first scans.</p>}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead><tr><th>Operation</th><th className="!text-right">Calls</th><th className="!text-right">p50</th><th className="!text-right">p95</th><th className="w-[30%]"><span className="sr-only">Distribution</span></th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.op}>
                  <td className="mono text-ink">{r.op}</td>
                  <td className="mono text-right">{r.n}</td>
                  <td className="mono text-right text-ink">{r.p50_ms} ms</td>
                  <td className="mono text-right">{r.p95_ms} ms</td>
                  <td aria-hidden>
                    <div className="relative mt-1.5 h-2 rounded bg-inset">
                      <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${(r.p95_ms / max) * 100}%`, background: "var(--hairline)" }} />
                      <span className="absolute inset-y-0 left-0 rounded" style={{ width: `${(r.p50_ms / max) * 100}%`, background: "var(--ink)" }} />
                    </div>
                  </td>
                </tr>))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
