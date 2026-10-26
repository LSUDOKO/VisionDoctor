import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, post, type Incident } from "../api";
import { CHECKS, Empty, ErrorNote, Icon, Skeleton, Tag, Tip, ago, errText, go, human, pct, useFeedback, type IconName } from "../ui";

const OPEN = ["open", "auto_repairing", "awaiting_approval", "dispatched"];
const STATE: Record<string, { icon: IconName; tone: string; text: string }> = {
  open: { icon: "alert", tone: "danger", text: "Open · agent working" },
  auto_repairing: { icon: "refresh", tone: "teal", text: "Auto-repairing" },
  awaiting_approval: { icon: "user", tone: "yellow", text: "Awaiting approval" },
  dispatched: { icon: "bolt", tone: "teal", text: "Technician dispatched" },
  repaired: { icon: "check", tone: "mint", text: "Repaired" },
  false_alarm: { icon: "dash", tone: "", text: "False alarm" },
  watch: { icon: "eye", tone: "warn", text: "Watching (low impact)" },
  closed: { icon: "check", tone: "", text: "Closed" },
};
type Act = "approve" | "reject" | "false_alarm";
const ACT: Record<Act, { title: string; body: string; confirm: string; done: string; danger?: boolean }> = {
  approve: { title: "Approve technician dispatch?", body: "A maintenance ticket is created and a technician is sent to this camera with the face-blurred evidence.", confirm: "Approve dispatch", done: "Dispatch approved" },
  reject: { title: "Reject this dispatch?", body: "No technician is sent. The incident stays open so the agent can keep watching the camera.", confirm: "Reject", done: "Dispatch rejected", danger: true },
  false_alarm: { title: "Mark as a false alarm?", body: "The incident closes and is counted as a false alarm. Corrections already applied stay in place.", confirm: "Mark false alarm", done: "Marked as false alarm", danger: true },
};

function IncidentCard({ inc }: { inc: Incident }) {
  const qc = useQueryClient();
  const { toast, confirm } = useFeedback();
  const act = useMutation({
    mutationFn: (what: Act) => post<{ error?: string }>(`/api/incidents/${inc.incident_id}/${what}`),
    onSuccess: (r, what) => {
      if (r?.error) toast({ title: "Action not applied", body: r.error, error: true });
      else toast({ title: ACT[what].done, body: `${inc.camera_id} · ${inc.incident_id}` });
      qc.invalidateQueries({ queryKey: ["incidents"] }); qc.invalidateQueries({ queryKey: ["summary"] });
    },
    onError: (e) => toast({ title: "Action failed", body: errText(e), error: true }),
  });
  const run = async (what: Act) => {
    const a = ACT[what];
    if (await confirm({ title: a.title, body: <><span className="mono text-xs">{inc.camera_id} · {inc.incident_id}</span><br />{a.body}</>, confirm: a.confirm, danger: a.danger })) act.mutate(what);
  };
  const st = STATE[inc.state] ?? { icon: "dash" as IconName, tone: "", text: human(inc.state) };
  const urls = inc.evidence_urls ?? [];
  const evidence = urls.find((u) => u.includes("_crop")) ?? urls[0];
  const sev = inc.severities && !Array.isArray(inc.severities) ? inc.severities : {};
  const pending = inc.approval?.state === "pending";
  const isOpen = OPEN.includes(inc.state);

  return (
    <article className="card grid gap-5 p-5 md:grid-cols-[15rem_minmax(0,1fr)]" style={pending ? { borderColor: "var(--ink)" } : undefined}
      aria-label={`Incident ${inc.incident_id} on ${inc.camera_id}`}>
      <div className="relative aspect-video overflow-hidden rounded-[10px] bg-inset md:aspect-[4/3]">
        {evidence ? <img src={evidence} alt={`${inc.camera_id} evidence (faces blurred), ${(inc.fault_types ?? []).join(", ") || "fault"}`} className="h-full w-full object-cover" loading="lazy" />
          : <div className="grid h-full place-items-center text-xs muted">no evidence image</div>}
        <span className="imgtag left-2"><Icon name="shield" size={10} className="mr-1 inline" />faces blurred</span>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Tag tone={st.tone}><Icon name={st.icon} size={12} />{st.text}</Tag>
          <a href={`#/camera/${inc.camera_id}`} className="font-semibold text-ink underline decoration-[var(--yellow)] decoration-2 underline-offset-[3px]">{inc.camera_id}</a>
          <span className="mono text-xs muted">{inc.incident_id} · opened {ago(inc.opened_at)}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {(inc.fault_types ?? []).map((f) => (
            <Tag key={f} tone="danger" mono>{CHECKS[f]?.label ?? human(f)}{sev[f] !== undefined ? ` · sev ${sev[f]}` : ""}</Tag>
          ))}
        </div>
        {inc.vlm_description && <p className="mt-3 border-l-2 border-ink pl-3 text-[15px] leading-relaxed text-ink">{inc.vlm_description}</p>}

        <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-[10px] bg-tint px-4 py-3" aria-label="Priority calculation">
          <div><div className="micro">Pred. drop</div><div className="big-num text-[22px] text-danger">{inc.predicted_drop != null ? `−${pct(inc.predicted_drop, 1)}` : "—"}</div></div>
          <span className="big-num text-lg muted" aria-hidden>×</span>
          <div><div className="micro">Criticality</div><div className="big-num text-[22px]">{inc.criticality ?? "—"}<span className="text-sm muted">/5</span></div></div>
          <span className="big-num text-lg muted" aria-hidden>=</span>
          <div><div className="flex items-center gap-1"><span className="micro">Priority</span><Tip text="Priority = predicted accuracy drop × camera criticality, as scored by the agent. Higher is more urgent; the queue is sorted by it." /></div>
            <div className="big-num text-[22px]"><span className="hl">{inc.priority_score?.toFixed(2) ?? "—"}</span></div></div>
        </div>

        {inc.approval && (
          <p className="mt-3 text-sm text-body">
            <span className="micro mr-1.5">Agent</span>recommends <span className="mono text-ink">{human(inc.approval.action ?? "action")}</span>
            {inc.approval.reason ? <span className="muted"> · {inc.approval.reason}</span> : null}
            <span className="muted"> · approval {inc.approval.state}{inc.approval.decided_by ? ` by ${inc.approval.decided_by}` : ""}</span>
          </p>
        )}
        {inc.ticket_id && <p className="mono mt-1 text-xs muted">ticket {inc.ticket_id}</p>}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          {pending && <>
            <button className="btn primary" disabled={act.isPending} onClick={() => run("approve")}><Icon name="check" /> Approve dispatch</button>
            <button className="btn" disabled={act.isPending} onClick={() => run("reject")}><Icon name="x" /> Reject</button>
          </>}
          {(pending || isOpen) && <button className="btn danger" disabled={act.isPending} onClick={() => run("false_alarm")}>Mark false alarm</button>}
          {inc.trace_id && <button className="btn ghost ml-auto" onClick={() => go(`traces/${inc.trace_id}`)}>View agent trace →</button>}
        </div>
        {act.error && <div className="mt-3"><ErrorNote error={act.error} /></div>}
      </div>
    </article>
  );
}

export default function Incidents() {
  const [all, setAll] = useState(false);
  const q = useQuery({ queryKey: ["incidents", all], queryFn: () => api<Incident[]>(all ? "/api/incidents" : "/api/incidents?state=open"), refetchInterval: 3000 });
  const rows = [...(q.data ?? [])].sort((a, b) =>
    Number(OPEN.includes(b.state)) - Number(OPEN.includes(a.state)) || (b.priority_score ?? 0) - (a.priority_score ?? 0));
  const waiting = rows.filter((i) => i.approval?.state === "pending").length;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="micro">Console</span>
          <h1 className="h-page mt-1">Incident queue</h1>
          <p className="mt-2 text-sm muted">Sorted by priority: predicted accuracy drop × camera criticality.{waiting > 0 && <> <span className="hl font-medium">{waiting} waiting for you.</span></>}</p>
        </div>
        <div className="seg" role="group" aria-label="Incident filter">
          <button aria-pressed={!all} onClick={() => setAll(false)}>Open</button>
          <button aria-pressed={all} onClick={() => setAll(true)}>History</button>
        </div>
      </div>
      {q.error && <ErrorNote error={q.error} />}
      {!q.data && !q.error && [0, 1].map((i) => <Skeleton key={i} className="h-56 w-full" />)}
      {q.data && rows.length === 0 && <Empty title={all ? "No incidents recorded" : "No open incidents"}>The fleet is healthy. New faults appear here the moment a scan finds them.</Empty>}
      <div className="space-y-4">{rows.map((i) => <IncidentCard key={i.incident_id} inc={i} />)}</div>
    </div>
  );
}
