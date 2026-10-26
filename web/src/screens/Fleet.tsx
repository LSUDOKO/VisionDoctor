import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, type Camera, type Status, type Summary } from "../api";
import { ACC_HINT, CHECKS, Empty, ErrorNote, Gauge, Icon, PillSelect, STATUS, Skeleton, Stat, StatusTag, Tag, Tip, ago, bust, go, human, pct } from "../ui";

const ORDER: Status[] = ["healthy", "watch", "repairing", "degraded", "failed"];
const BAR: Record<Status, string> = { healthy: "var(--ink)", watch: "var(--yellow)", repairing: "var(--teal-ink)", degraded: "#e9a17c", failed: "var(--failed-bar)" };

function SummaryBand({ s }: { s: Summary }) {
  const acc = s.predicted_fleet_accuracy;
  return (
    <section className="card grid gap-8 p-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:p-8" aria-label="Fleet summary">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="micro">Predicted fleet accuracy</span>
          <Tip text="Average predicted accuracy: how well the detection AI across all cameras is likely working right now, estimated without labels." />
        </div>
        <div className="mt-3 flex items-baseline gap-1" data-testid="fleet-accuracy">
          <span className="big-num text-[clamp(60px,9vw,96px)]">{acc == null ? "—" : (acc * 100).toFixed(1)}</span>
          {acc != null && <span className="big-num text-[clamp(28px,4vw,40px)] text-label">%</span>}
        </div>
        <div className="mt-5"><Gauge value={acc} label="Predicted fleet accuracy" /></div>
        <div className="mt-5">
          <div className="stackbar" aria-hidden>
            {ORDER.filter((k) => s.by_status[k]).map((k) => <i key={k} style={{ flex: s.by_status[k], background: BAR[k] }} />)}
          </div>
          <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs" aria-label="Cameras by status">
            {ORDER.map((k) => (
              <li key={k} className="flex items-center gap-1.5">
                <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: BAR[k] }} />
                <span className="text-ink">{STATUS[k].label}</span> <span className="mono muted">{s.by_status[k] ?? 0}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-7 border-hairline lg:border-l lg:pl-8">
        <Stat label="Healthy" value={`${s.healthy_pct.toFixed(0)}%`} sub={`of ${s.cameras} cameras`} hint="Share of cameras whose image-quality checks all pass right now." />
        <Stat label="Open incidents" value={<span className={s.open_incidents ? "text-danger" : ""}>{s.open_incidents}</span>} sub={<a className="linkish" href="#/incidents">view queue</a>}
          hint="Problems currently being handled by the agent or waiting on a person." />
        <Stat label="Awaiting approval" value={s.awaiting_approval ? <span className="hl">{s.awaiting_approval}</span> : 0} sub="technician dispatches"
          hint="Incidents where the agent recommends a technician visit and needs a person to approve it." />
        <Stat label="Auto-fixed today" value={s.auto_fixed_today} sub={`${s.false_alarms_today} false alarms`}
          hint="Incidents in the last 24 h repaired by software correction alone, with no truck roll." />
        <div className="col-span-2 flex flex-wrap items-center gap-2">
          <span className="micro">Runtime</span>
          <Tag tone={s.is_cool ? "yellow" : "line"} mono title="COOL = OpenCV-optimized build. Shows whether the scanner runs on the accelerated build.">
            {s.is_cool ? "COOL build ✓" : "stock OpenCV 5"}
          </Tag>
        </div>
      </div>
    </section>
  );
}

function SummarySkeleton() {
  return (
    <div className="card grid gap-8 p-8 lg:grid-cols-2" aria-busy="true" aria-label="Loading fleet summary">
      <div><Skeleton className="h-3 w-40" /><Skeleton className="mt-4 h-20 w-64" /><Skeleton className="mt-6 h-2.5 w-full" /></div>
      <div className="grid grid-cols-2 gap-6">{[0, 1, 2, 3].map((i) => <div key={i}><Skeleton className="h-3 w-24" /><Skeleton className="mt-3 h-8 w-16" /></div>)}</div>
    </div>
  );
}

const faultsOf = (c: Camera) =>
  (c.top_faults ?? []).map((f) => (typeof f === "string" ? f : (f as { type?: string }).type)).filter((f): f is string => !!f);

function CameraCard({ c }: { c: Camera }) {
  const faults = faultsOf(c);
  const label = `${c.name}, ${STATUS[c.status]?.label ?? c.status}${faults.length ? `, ${faults.join(", ")}` : ""}`;
  const src = bust(c.thumbnail_url, c.last_scan_at);
  return (
    <a href={`#/camera/${c.camera_id}`} data-testid="camera-tile" aria-label={`Open ${label}`} className="card hover group block overflow-hidden no-underline">
      <div className="sweep relative aspect-video bg-inset">
        {src && <img src={src} alt={`${c.camera_id} live view${faults.length ? `, ${faults.join(", ")} detected` : ""}`} className="h-full w-full object-cover" loading="lazy" />}
        <span className="imgtag left-2.5">{c.camera_id}</span>
        <span className="absolute right-2.5 top-2.5 rounded-full bg-page"><StatusTag status={c.status} sm /></span>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold text-ink">{c.name}</div>
            <div className="mt-0.5 truncate text-xs muted">{c.site} · scanned {ago(c.last_scan_at)}</div>
          </div>
          <div className="text-right" title={ACC_HINT}>
            <div className="big-num text-[26px]">{pct(c.predicted_ai_accuracy)}</div>
            <div className="micro whitespace-nowrap !text-[10px]">pred. accuracy</div>
          </div>
        </div>
        <div className="mt-3"><Gauge value={c.predicted_ai_accuracy} label={`${c.name} predicted accuracy`} sm /></div>
        <div className="mt-3 flex min-h-[24px] flex-wrap gap-1.5">
          {faults.length ? faults.slice(0, 3).map((f) => <Tag key={f} tone="danger" mono>{CHECKS[f]?.label ?? human(f)}</Tag>)
            : <span className="text-xs muted">No faults detected</span>}
        </div>
      </div>
    </a>
  );
}

export default function Fleet() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api<Summary>("/api/summary"), refetchInterval: 3000 });
  const cams = useQuery({ queryKey: ["cameras"], queryFn: () => api<Camera[]>("/api/cameras"), refetchInterval: 3000 });
  const [site, setSite] = useState("");
  const [status, setStatus] = useState("");
  const sites = useMemo(() => [...new Set((cams.data ?? []).map((c) => c.site))].sort(), [cams.data]);
  const shown = (cams.data ?? []).filter((c) => (!site || c.site === site) && (!status || c.status === status));

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="micro">Console</span>
          <h1 className="h-page mt-1">Fleet</h1>
        </div>
        <p className="max-w-md text-sm muted">Every camera is re-scanned on a schedule; numbers refresh live.</p>
      </div>
      {summary.data ? <SummaryBand s={summary.data} /> : summary.error ? <ErrorNote error={summary.error} /> : <SummarySkeleton />}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="h-card !text-lg">Cameras <span className="mono text-sm font-normal muted">{shown.length}/{cams.data?.length ?? 0}</span></h2>
        <div className="flex flex-wrap gap-2">
          <PillSelect label="Filter by site" value={site} onChange={setSite} options={[{ value: "", label: "All sites" }, ...sites.map((s) => ({ value: s, label: s }))]} />
          <PillSelect label="Filter by status" value={status} onChange={setStatus}
            options={[{ value: "", label: "Any status" }, ...ORDER.map((s) => ({ value: s, label: STATUS[s].label }))]} />
        </div>
      </div>
      {cams.error && <ErrorNote error={cams.error} />}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {!cams.data && !cams.error && [0, 1, 2, 3].map((i) => (
          <div key={i} className="card overflow-hidden" aria-hidden><Skeleton className="aspect-video !rounded-none" /><div className="p-4"><Skeleton className="h-4 w-2/3" /><Skeleton className="mt-2 h-3 w-1/2" /><Skeleton className="mt-4 h-1.5 w-full" /></div></div>
        ))}
        {shown.map((c) => <CameraCard key={c.camera_id} c={c} />)}
      </div>
      {cams.data && shown.length === 0 && (
        <Empty icon={cams.data.length ? "scan" : "eye"} title={cams.data.length ? "No cameras match these filters" : "No cameras yet"}>
          {cams.data.length ? <button className="linkish" onClick={() => { setSite(""); setStatus(""); }}>Clear filters</button> : "Cameras appear here after their first scan."}
        </Empty>
      )}
      <p className="text-xs muted"><Icon name="eye" size={12} className="mr-1 inline" />Thumbnails are live frames. Tap a camera for its checks, history and corrections. <button className="linkish" onClick={() => go("docs")}>What do the checks mean?</button></p>
    </div>
  );
}
