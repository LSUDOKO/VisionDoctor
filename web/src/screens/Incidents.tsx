import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, post, type Incident } from "../api";
import { ErrorNote, Loading, ago, go, pct } from "../ui";

const OPEN = ["open", "auto_repairing", "awaiting_approval", "dispatched"];
const STATE: Record<string, { icon: string; cls: string; text: string }> = {
  open: { icon: "●", cls: "text-bad border-bad/40", text: "Open — agent working" },
  auto_repairing: { icon: "⟳", cls: "text-info border-info/40", text: "Auto-repairing" },
  awaiting_approval: { icon: "?", cls: "text-warn border-warn/40", text: "Awaiting approval" },
  dispatched: { icon: "➜", cls: "text-info border-info/40", text: "Technician dispatched" },
  repaired: { icon: "✓", cls: "text-ok border-ok/40", text: "Repaired" },
  false_alarm: { icon: "∅", cls: "text-muted border-line", text: "False alarm" },
  watch: { icon: "◐", cls: "text-warn border-warn/40", text: "Watching (low impact)" },
  closed: { icon: "■", cls: "text-muted border-line", text: "Closed" },
};

function Card({ inc }: { inc: Incident }) {
  const qc = useQueryClient();
  const [msg, setMsg] = useState<string | null>(null);
  const act = useMutation({
    mutationFn: (what: "approve" | "reject" | "false_alarm") => post<{ error?: string }>(`/api/incidents/${inc.incident_id}/${what}`),
    onSuccess: (r) => { setMsg(r?.error ?? null); qc.invalidateQueries({ queryKey: ["incidents"] }); qc.invalidateQueries({ queryKey: ["summary"] }); },
  });
  const st = STATE[inc.state] ?? { icon: "•", cls: "text-muted border-line", text: inc.state };
  const urls = inc.evidence_urls ?? [];
  const evidence = urls.find((u) => u.includes("_crop")) ?? urls[0];
  const sev = inc.severities && !Array.isArray(inc.severities) ? inc.severities : {};
  const faults = (inc.fault_types ?? []).map((f) => `${f}${sev[f] !== undefined ? ` sev ${sev[f]}` : ""}`);
  const pending = inc.approval?.state === "pending";
  const isOpen = OPEN.includes(inc.state);

  return (
    <article className={`panel grid gap-4 p-4 md:grid-cols-[14rem_minmax(0,1fr)] ${pending ? "border-warn/60" : ""}`} aria-label={`Incident ${inc.incident_id} on ${inc.camera_id}`}>
      <div className="aspect-video overflow-hidden rounded-md border border-line bg-raised">
        {evidence ? <img src={evidence} alt={`${inc.camera_id} evidence, ${faults.join(", ") || "fault"}`} className="h-full w-full object-cover" loading="lazy" />
          : <div className="grid h-full place-items-center text-xs text-muted">no evidence image</div>}
      </div>
      <div className="min-w-0 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-semibold ${st.cls}`}><span aria-hidden>{st.icon}</span>{st.text}</span>
          <a href={`#/camera/${inc.camera_id}`} className="font-semibold hover:text-accent">{inc.camera_id}</a>
          <span className="font-mono text-xs text-muted">{inc.incident_id} · opened {ago(inc.opened_at)}</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {faults.map((f) => <span key={f} className="rounded bg-raised px-1.5 py-0.5 font-mono text-xs">{f}</span>)}
        </div>
        {inc.vlm_description && <blockquote className="border-l-2 border-accent pl-3 text-sm italic">“{inc.vlm_description}”</blockquote>}
        <dl className="grid grid-cols-3 gap-2 text-sm sm:max-w-md">
          <div title="Predicted drop: how many accuracy points the detection AI is likely losing because of this fault."><dt className="label">Pred. drop</dt><dd className="num font-semibold text-bad">{inc.predicted_drop != null ? `−${pct(inc.predicted_drop, 1)}` : "—"}</dd></div>
          <div title="Priority = predicted accuracy drop × camera criticality. Higher is more urgent."><dt className="label">Priority</dt><dd className="num font-semibold">{inc.priority_score?.toFixed(2) ?? "—"}</dd></div>
          <div title="How important this camera is, from 1 (low) to 5 (critical)."><dt className="label">Criticality</dt><dd className="num font-semibold">{inc.criticality ?? "—"}/5</dd></div>
        </dl>
        {inc.approval && (
          <p className="text-xs text-muted">Agent recommends <span className="font-mono text-fg">{inc.approval.action ?? "action"}</span>
            {inc.approval.reason ? ` — ${inc.approval.reason}` : ""} · approval {inc.approval.state}{inc.approval.decided_by ? ` by ${inc.approval.decided_by}` : ""}</p>
        )}
        {inc.ticket_id && <p className="font-mono text-xs text-muted">ticket {inc.ticket_id}</p>}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {pending && <>
            <button className="btn btn-primary" disabled={act.isPending} onClick={() => act.mutate("approve")}>✓ Approve dispatch</button>
            <button className="btn" disabled={act.isPending} onClick={() => act.mutate("reject")}>✕ Reject</button>
          </>}
          {(pending || isOpen) && <button className="btn btn-danger" disabled={act.isPending} onClick={() => act.mutate("false_alarm")}>∅ Mark false alarm</button>}
          {inc.trace_id && <button className="ml-auto text-sm text-accent underline-offset-2 hover:underline" onClick={() => go(`traces/${inc.trace_id}`)}>View trace →</button>}
        </div>
        {act.error && <ErrorNote error={act.error} />}
        {msg && <ErrorNote error={msg} />}
      </div>
    </article>
  );
}

export default function Incidents() {
  const [all, setAll] = useState(false);
  const q = useQuery({ queryKey: ["incidents", all], queryFn: () => api<Incident[]>(all ? "/api/incidents" : "/api/incidents?state=open"), refetchInterval: 3000 });
  const rows = [...(q.data ?? [])].sort((a, b) =>
    Number(OPEN.includes(b.state)) - Number(OPEN.includes(a.state)) || (b.priority_score ?? 0) - (a.priority_score ?? 0));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Incident queue</h2>
        <div role="group" aria-label="Incident filter" className="inline-flex rounded-md border border-line p-0.5">
          {[false, true].map((v) => (
            <button key={String(v)} aria-pressed={all === v} onClick={() => setAll(v)}
              className={`rounded px-3 py-1 text-sm ${all === v ? "bg-accent/15 text-accent" : "text-muted hover:text-fg"}`}>{v ? "History (all)" : "Open"}</button>
          ))}
        </div>
      </div>
      <p className="text-sm text-muted">Sorted by priority (predicted accuracy drop × camera criticality).</p>
      {q.error && <ErrorNote error={q.error} />}
      {!q.data && !q.error && <Loading what="incidents" />}
      {q.data && rows.length === 0 && <div className="panel p-8 text-center text-sm text-muted">✓ No {all ? "" : "open "}incidents. The fleet is healthy.</div>}
      <div className="space-y-3">{rows.map((i) => <Card key={i.incident_id} inc={i} />)}</div>
    </div>
  );
}
