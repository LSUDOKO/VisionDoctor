import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api, type Camera, type Status, type Summary } from "../api";
import { ACC_HINT, ErrorNote, Loading, STATUS, Stat, StatusChip, ago, go, pct } from "../ui";

function SummaryBar({ s }: { s: Summary }) {
  return (
    <div className="panel grid grid-cols-2 divide-line sm:grid-cols-3 lg:grid-cols-6 lg:divide-x">
      <Stat label="Healthy" value={`${s.healthy_pct.toFixed(0)}%`} tone={s.healthy_pct >= 90 ? "text-ok" : s.healthy_pct >= 60 ? "text-warn" : "text-crit"}
        hint={`Share of the ${s.cameras} cameras whose image-quality checks all pass right now.`} />
      <Stat label="Fleet accuracy" value={pct(s.predicted_fleet_accuracy, 1)}
        hint="Average predicted accuracy: how well the detection AI across all cameras is likely working right now, estimated without labels." />
      <Stat label="Open incidents" value={s.open_incidents} tone={s.open_incidents ? "text-bad" : ""}
        hint="Problems currently being handled by the agent or waiting on a person." />
      <Stat label="Awaiting approval" value={s.awaiting_approval} tone={s.awaiting_approval ? "text-warn" : ""}
        hint="Incidents where the agent recommends a technician visit and needs a person to approve it." />
      <Stat label="Auto-fixed today" value={s.auto_fixed_today} tone={s.auto_fixed_today ? "text-ok" : ""}
        hint="Incidents in the last 24 h repaired by software correction alone, with no truck roll." />
      <div className="px-4 py-3" title="COOL = OpenCV-optimized build (OpenCV AI Competition). Shows whether the scanner runs on the accelerated build.">
        <div className="label">Runtime</div>
        <div className={`mt-2 inline-flex rounded border px-2 py-0.5 font-mono text-xs font-semibold ${s.is_cool ? "border-accent/50 text-accent" : "border-line text-muted"}`}>
          {s.is_cool ? "COOL build ✓" : "stock OpenCV"}
        </div>
      </div>
    </div>
  );
}

function Tile({ c }: { c: Camera }) {
  const faults = (c.top_faults ?? []).map((f) => (typeof f === "string" ? f : (f as { type?: string }).type)).filter(Boolean);
  const label = `${c.name}, ${STATUS[c.status]?.label ?? c.status}${faults.length ? `, ${faults.join(", ")}` : ""}`;
  return (
    <button data-testid="camera-tile" onClick={() => go(`camera/${c.camera_id}`)} aria-label={`Open ${label}`}
      className="panel group overflow-hidden text-left transition-colors hover:border-accent">
      <div className="relative aspect-video bg-raised scan-sweep">
        {c.thumbnail_url && (
          <img src={c.thumbnail_url.includes("?") ? c.thumbnail_url /* presigned S3: never alter */ : `${c.thumbnail_url}?t=${Math.floor(c.last_scan_at ?? 0)}`} alt={`${c.camera_id} live view${faults.length ? `, ${faults.join(", ")} detected` : ""}`}
            className="h-full w-full object-cover" loading="lazy" />
        )}
        <span className="absolute left-2 top-2 rounded bg-bg/80 px-1.5 py-0.5 font-mono text-[11px] text-fg">{c.camera_id}</span>
        <span className="absolute right-2 top-2 rounded bg-bg/90"><StatusChip status={c.status} /></span>
      </div>
      <div className="flex items-end justify-between gap-2 p-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{c.name}</div>
          <div className="truncate text-xs text-muted" title="Time since the last health scan">
            {c.site} · scanned {ago(c.last_scan_at)}
          </div>
          {faults.length > 0 && <div className="mt-1 truncate font-mono text-[11px] text-bad">{faults.join(" · ")}</div>}
        </div>
        <div className="text-right" title={ACC_HINT}>
          <div className="num text-xl font-semibold">{pct(c.predicted_ai_accuracy)}</div>
          <div className="text-[10px] uppercase tracking-wider text-muted">pred. AI acc.</div>
        </div>
      </div>
    </button>
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
    <div className="space-y-6">
      {summary.data ? <SummaryBar s={summary.data} /> : summary.error ? <ErrorNote error={summary.error} /> : <Loading what="summary" />}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 className="text-xl font-semibold">Camera fleet <span className="num text-sm text-muted">({shown.length}/{cams.data?.length ?? 0})</span></h2>
        <div className="flex flex-wrap gap-2">
          <label className="flex items-center gap-2 text-sm text-muted">Site
            <select className="field" value={site} onChange={(e) => setSite(e.target.value)}>
              <option value="">All sites</option>
              {sites.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-muted">Status
            <select className="field" value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="">All</option>
              {(Object.keys(STATUS) as Status[]).map((s) => <option key={s} value={s}>{STATUS[s].icon} {STATUS[s].label}</option>)}
            </select>
          </label>
        </div>
      </div>
      {cams.error && <ErrorNote error={cams.error} />}
      {!cams.data && !cams.error && <Loading what="cameras" />}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {shown.map((c) => <Tile key={c.camera_id} c={c} />)}
      </div>
      {cams.data && shown.length === 0 && <p className="text-sm text-muted">No cameras match these filters.</p>}
    </div>
  );
}
