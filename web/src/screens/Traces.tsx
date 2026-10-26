import { useQuery } from "@tanstack/react-query";
import { api, type Trace } from "../api";
import { Empty, ErrorNote, Icon, Skeleton, Tag, Tip, ago, go, human, ms } from "../ui";

const blocked = (g: string) => !/^(allowed|ok|allow|pass)/i.test(g);

function TraceView({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["trace", id], queryFn: () => api<Trace>(`/api/traces/${id}`), refetchInterval: 5000 });
  if (q.error) return <ErrorNote error={q.error} />;
  if (!q.data) return <div className="space-y-3"><Skeleton className="h-28 w-full" />{[0, 1, 2].map((i) => <Skeleton key={i} className="h-20 w-full" />)}</div>;
  const t = q.data;
  const changed = t.steps.filter((s) => s.changed_plan).length;
  const nBlocked = t.steps.filter((s) => blocked(s.guard)).length;
  return (
    <div className="space-y-5">
      <section className="card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Tag tone="yellow" mono>{t.agent}{t.model ? ` · ${t.model}` : ""}</Tag>
          <Tag tone="line" mono>{t.trace_id}</Tag>
          <a href={`#/camera/${t.camera_id}`} className="tag line mono no-underline hover:border-[var(--ink)]">{t.camera_id}</a>
          <span className="ml-auto text-xs muted">started {ago(t.started)}</span>
        </div>
        <h2 className="display mt-4 text-2xl">{human(t.outcome)}</h2>
        <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div><dt className="micro">Total time</dt><dd className="big-num mt-1 text-xl">{ms(t.total_ms)}</dd></div>
          <div><dt className="micro">Tool calls</dt><dd className="big-num mt-1 text-xl">{t.steps.length}</dd></div>
          <div><dt className="micro">Plan changes</dt><dd className="big-num mt-1 text-xl">{changed}</dd></div>
          <div><dt className="flex items-center gap-1"><span className="micro">Tokens</span><Tip text="LLM tokens in / out. Zero for the deterministic policy agent." align="end" /></dt>
            <dd className="big-num mt-1 text-xl">{t.tokens_in ?? 0}<span className="text-sm muted"> / {t.tokens_out ?? 0}</span></dd></div>
        </dl>
        {nBlocked > 0 && <p className="mt-3 text-sm text-danger"><Icon name="shield" size={13} className="mr-1 inline" />The guard blocked {nBlocked} call{nBlocked > 1 ? "s" : ""} in this run.</p>}
      </section>

      <ol className="log" aria-label="Execution log">
        {t.steps.map((s) => {
          const bad = blocked(s.guard);
          return (
            <li key={s.i} className={`logstep${bad ? " blocked" : s.changed_plan ? " changed" : ""}`}>
              <span className="logn" aria-hidden>{String(s.i).padStart(2, "0")}</span>
              <div className="logbody min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="mono text-[13.5px] font-medium text-ink">{s.tool}</span>
                  {s.changed_plan && <span className="tag yellow sm"><Icon name="bolt" size={11} />OpenCV result changed the plan</span>}
                  <span className={`tag sm ${bad ? "failed" : "mint"}`} title="Guard verdict: the safety layer checks every tool call against policy before it runs.">
                    <Icon name={bad ? "x" : "check"} size={11} />guard · {s.guard}
                  </span>
                  <span className="mono ml-auto text-xs muted" title="Tool latency">{ms(s.latency_ms)}</span>
                </div>
                <p className="mono mt-2 break-words text-[12.5px] leading-relaxed text-body">{s.output_summary}</p>
                {s.decision_reason && <p className="mt-1.5 text-sm text-body"><span className="font-semibold text-ink">Why:</span> {s.decision_reason}</p>}
              </div>
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
    <div className="space-y-6">
      <div>
        <span className="micro">Console</span>
        <h1 className="h-page mt-1">Agent traces</h1>
        <p className="mt-2 max-w-2xl text-sm muted">Every agent run, step by step: the MCP tool it called, what came back, why it chose it, and the guard&apos;s verdict.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[19rem_minmax(0,1fr)]">
        <nav aria-label="Trace list" className={`card max-h-[75vh] overflow-y-auto p-1.5 ${id ? "hidden lg:block" : ""}`}>
          {list.error && <ErrorNote error={list.error} />}
          {!list.data && !list.error && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="m-1 h-14" />)}
          {list.data?.length === 0 && <p className="p-4 text-sm muted">No agent runs yet. Inject a fault from Demo.</p>}
          {list.data?.map((t) => {
            const on = t.trace_id === id;
            return (
              <button key={t.trace_id} onClick={() => go(`traces/${t.trace_id}`)} aria-current={on ? "true" : undefined}
                className={`block w-full rounded-[8px] px-3 py-2.5 text-left transition-colors ${on ? "bg-yellow text-forest" : "hover:bg-tint"}`}>
                <div className="flex justify-between gap-2 text-sm"><span className="font-semibold">{t.camera_id}</span><span className={`text-xs ${on ? "" : "muted"}`}>{ago(t.started)}</span></div>
                <div className={`mono mt-0.5 flex justify-between gap-2 text-[11px] ${on ? "" : "muted"}`}>
                  <span className="truncate">{human(t.outcome)}</span>
                  <span className="flex-none">{t.steps.length} steps{t.steps.some((s) => s.changed_plan) ? " ★" : ""}</span>
                </div>
              </button>
            );
          })}
        </nav>
        <div className="min-w-0">
          {id && <a href="#/traces" className="btn ghost sm -ml-2 mb-3 lg:hidden"><Icon name="back" /> All traces</a>}
          {id ? <TraceView id={id} /> : (
            <Empty icon="bolt" title="Select a trace">Pick a run to see each tool call, its result, the agent&apos;s reasoning and the guard verdict. Steps where an OpenCV result changed the plan are highlighted.</Empty>
          )}
        </div>
      </div>
    </div>
  );
}
