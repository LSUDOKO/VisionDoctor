import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type OpMetrics } from "../api";
import { ErrorNote, Loading, Section, chartColors } from "../ui";

type Row = Record<string, unknown>;
const tooltipStyle = { background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", color: "rgb(var(--fg))", fontSize: 12 };
const PALETTE = [chartColors.accent, chartColors.warn, chartColors.ok, chartColors.muted];

/** Bench output shape is not fixed: chart any array of objects with a label key and numeric *_ms fields. */
function BenchTable({ name, rows }: { name: string; rows: Row[] }) {
  const labelKey = Object.keys(rows[0]).find((k) => typeof rows[0][k] === "string") ?? "";
  const numKeys = Object.keys(rows[0]).filter((k) => typeof rows[0][k] === "number");
  const msKeys = numKeys.filter((k) => /ms|speedup/i.test(k)).slice(0, 4);
  return (
    <Section title={name}>
      {labelKey && msKeys.length > 0 && (
        <div className="mb-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 80, left: 0 }}>
              <CartesianGrid stroke={chartColors.line} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={labelKey} stroke={chartColors.muted} fontSize={11} angle={-35} textAnchor="end" interval={0} />
              <YAxis stroke={chartColors.muted} fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} verticalAlign="top" />
              {msKeys.map((k, i) => <Bar key={k} dataKey={k} fill={PALETTE[i]} isAnimationActive={false} />)}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left">{[labelKey, ...numKeys].filter(Boolean).map((k) => <th key={k} className="label px-2 py-1.5">{k}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => (
            <tr key={i} className="border-t border-line">
              {labelKey && <td className="px-2 py-1.5 font-mono">{String(r[labelKey])}</td>}
              {numKeys.map((k) => <td key={k} className="num px-2 py-1.5">{Number(r[k]).toFixed(3).replace(/\.?0+$/, "")}</td>)}
            </tr>))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

function Bench() {
  const q = useQuery({ queryKey: ["bench"], queryFn: () => api<Row>("/api/bench") });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <Loading what="benchmarks" />;
  if (q.data.available === false) return <Section title="COOL vs baseline"><p className="text-sm text-muted">No benchmark results yet. Run the bench script to compare the COOL build against stock OpenCV.</p></Section>;
  const tables = Object.entries(q.data).filter(([, v]) => Array.isArray(v) && v.length > 0 && typeof v[0] === "object") as [string, Row[]][];
  const scalars = Object.entries(q.data).filter(([, v]) => typeof v === "number" || typeof v === "string" || typeof v === "boolean");
  return (
    <div className="space-y-5">
      {scalars.length > 0 && (
        <div className="panel grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
          {scalars.map(([k, v]) => <div key={k}><div className="label">{k.replace(/_/g, " ")}</div><div className="num text-lg font-semibold">{String(v)}</div></div>)}
        </div>
      )}
      {tables.map(([k, rows]) => <BenchTable key={k} name={k.replace(/_/g, " ")} rows={rows} />)}
    </div>
  );
}

export default function Performance() {
  const ops = useQuery({ queryKey: ["ops"], queryFn: () => api<OpMetrics>("/api/metrics/ops"), refetchInterval: 5000 });
  const rows = Object.entries(ops.data ?? {}).map(([op, m]) => ({ op, ...m })).sort((a, b) => b.p50_ms - a.p50_ms);
  return (
    <div className="space-y-5">
      <h2 className="text-xl font-semibold">Performance</h2>
      <Bench />
      <Section title="Live OpenCV op latency (this process)">
        {ops.error && <ErrorNote error={ops.error} />}
        {!ops.data && !ops.error && <Loading what="op metrics" />}
        {rows.length > 0 && <>
          <div className="mb-4 h-80" role="img" aria-label={`Median latency per OpenCV operation; slowest is ${rows[0].op} at ${rows[0].p50_ms} ms`}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 80, left: 0 }}>
                <CartesianGrid stroke={chartColors.line} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="op" stroke={chartColors.muted} fontSize={11} angle={-35} textAnchor="end" interval={0} />
                <YAxis stroke={chartColors.muted} fontSize={11} scale="log" domain={["auto", "auto"]} allowDataOverflow tickFormatter={(v: number) => `${v} ms`} />
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${v} ms`} />
                <Bar dataKey="p50_ms" name="median (p50)" fill={chartColors.accent} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left">
                <th className="label px-2 py-1.5">Operation</th>
                <th className="label px-2 py-1.5 text-right" title="How many times this op ran">Calls</th>
                <th className="label px-2 py-1.5 text-right" title="Median: half of the calls were faster than this">p50</th>
                <th className="label px-2 py-1.5 text-right" title="95th percentile: only 1 in 20 calls was slower than this">p95</th>
              </tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.op} className="border-t border-line">
                  <td className="px-2 py-1.5 font-mono">{r.op}</td>
                  <td className="num px-2 py-1.5 text-right">{r.n}</td>
                  <td className="num px-2 py-1.5 text-right">{r.p50_ms} ms</td>
                  <td className="num px-2 py-1.5 text-right">{r.p95_ms} ms</td>
                </tr>))}
              </tbody>
            </table>
          </div>
        </>}
      </Section>
    </div>
  );
}
