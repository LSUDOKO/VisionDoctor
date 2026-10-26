import { useQuery } from "@tanstack/react-query";
import { api, type Trace } from "../api";
import { ErrorNote, Loading, ago, go, ms } from "../ui";

const blocked = (g: string) => !/^(allowed|ok|allow|pass)/i.test(g);

function TraceView({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["trace", id], queryFn: () => api<Trace>(`/api/traces/${id}`), refetchInterval: 5000 });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <Loading what="trace" />;
  const t = q.data;
  return (
    <div className="space-y-4">
      <div className="panel grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-6">
        {[
          ["Trace", t.trace_id, "Unique id of this agent run."],
          ["Camera", t.camera_id, "Camera the agent was investigating."],
          ["Agent", `${t.agent}${t.model ? ` · ${t.model}` : ""}`, "Which agent ran (LLM-based or rule-based policy) and its model."],
          ["Outcome", t.outcome.replace(/_/g, " "), "How the agent closed the incident."],
          ["Total", ms(t.total_ms), "Wall-clock time from incident open to the agent's decision."],
          ["Tokens", `${t.tokens_in ?? 0} in / ${t.tokens_out ?? 0} out`, "LLM tokens used (0 for the rule-based policy agent)."],
        ].map(([l, v, h]) => (
          <div key={l} title={h} className="min-w-0"><div className="label">{l}</div><div className="num truncate text-sm font-semibold">{v}</div></div>
        ))}
      </div>
      <ol className="relative ml-3 space-y-3 border-l border-line pl-6">
        {t.steps.map((s) => {
          const bad = blocked(s.guard);
          return (
            <li key={s.i} className={`panel relative p-3 ${bad ? "border-crit/70 bg-crit/5" : s.changed_plan ? "border-accent/70" : ""}`}>
              <span aria-hidden className={`absolute -left-[2.15rem] top-3 grid h-6 w-6 place-items-center rounded-full border text-[11px] font-semibold num ${bad ? "border-crit bg-crit/20 text-crit" : s.changed_plan ? "border-accent bg-accent/20 text-accent" : "border-line bg-panel text-muted"}`}>{s.i}</span>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-sm font-semibold">{s.tool}</span>
                {s.changed_plan && <span className="rounded border border-accent/60 bg-accent/10 px-1.5 py-0.5 text-[11px] font-semibold text-accent">★ OpenCV result changed the plan</span>}
                <span className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold ${bad ? "border-crit/60 text-crit" : "border-ok/40 text-ok"}`}
                  title="Guard verdict: the safety layer that checks every tool call against policy before it runs.">
                  {bad ? "✕" : "✓"} guard: {s.guard}
                </span>
                <span className="num ml-auto text-xs text-muted" title="Time this tool call took">{ms(s.latency_ms)}</span>
              </div>
              <p className="mt-1.5 break-words font-mono text-xs">{s.output_summary}</p>
              {s.decision_reason && <p className="mt-1 text-sm text-muted"><span className="text-fg">Why:</span> {s.decision_reason}</p>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function Traces({ id }: { id?: string }) {
  const list = useQuery({ queryKey: ["traces"], queryFn: () => api<Trace[]>("/api/traces"), refetchInterval: 5000 });
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">Agent traces</h2>
      <div className="grid gap-5 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <nav aria-label="Trace list" className="panel max-h-[70vh] overflow-y-auto p-1">
          {list.error && <ErrorNote error={list.error} />}
          {!list.data && !list.error && <Loading what="traces" />}
          {list.data?.length === 0 && <p className="p-4 text-sm text-muted">No agent runs yet. Inject a fault from Demo control.</p>}
          {list.data?.map((t) => (
            <button key={t.trace_id} onClick={() => go(`traces/${t.trace_id}`)} aria-current={t.trace_id === id}
              className={`block w-full rounded-md px-3 py-2 text-left ${t.trace_id === id ? "bg-accent/15" : "hover:bg-raised"}`}>
              <div className="flex justify-between gap-2 text-sm"><span className="font-semibold">{t.camera_id}</span><span className="text-xs text-muted">{ago(t.started)}</span></div>
              <div className="flex justify-between gap-2 font-mono text-[11px] text-muted">
                <span>{t.outcome.replace(/_/g, " ")}</span>
                <span>{t.steps.length} steps{t.steps.some((s) => s.changed_plan) ? " ★" : ""}</span>
              </div>
            </button>
          ))}
        </nav>
        <div className="min-w-0">{id ? <TraceView id={id} /> : <p className="panel p-8 text-center text-sm text-muted">Select a trace to see each tool call, its result, the agent's reasoning and the guard verdict.</p>}</div>
      </div>
    </div>
  );
}
