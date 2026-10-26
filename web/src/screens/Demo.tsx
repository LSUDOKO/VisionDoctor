import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, post, type Camera } from "../api";
import { Card, ErrorNote, Icon, Skeleton, errText, human, useFeedback } from "../ui";

const FAULTS = ["drift", "vibration", "haze", "condensation", "glare", "exposure", "color_cast", "ir_cut_stuck", "noise",
  "occlusion", "smudge", "spider_web", "defocus", "freeze", "dead"];
const SEV_WORD = ["", "barely visible", "mild", "clear", "strong", "severe"];

export default function Demo() {
  const qc = useQueryClient();
  const { toast } = useFeedback();
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<string[]>("/api/scenarios") });
  const cams = useQuery({ queryKey: ["cameras"], queryFn: () => api<Camera[]>("/api/cameras") });
  const run = useMutation({
    mutationFn: (name: string) => post<{ events?: number }>("/api/sim/scenario", { name }),
    onSuccess: (r, name) => toast({ title: `Scenario “${name}” started`, body: `${r?.events ?? "Several"} fault events scheduled. Watch the fleet and incident queue.` }),
    onError: (e) => toast({ title: "Could not start scenario", body: errText(e), error: true }),
  });
  const inject = useMutation({
    mutationFn: (b: Record<string, unknown>) => post<{ event_id?: string }>("/api/sim/inject", b),
    onSuccess: (r, b) => {
      toast({ title: "Fault injected", body: `${human(String(b.fault))} sev ${b.severity} on ${b.camera_id}${r?.event_id ? ` · ${r.event_id}` : ""}. The next scan should catch it.` });
      qc.invalidateQueries({ queryKey: ["cameras"] });
    },
    onError: (e) => toast({ title: "Inject failed", body: errText(e), error: true }),
  });
  const [form, setForm] = useState({ camera_id: "", fault: "haze", severity: 3, duration_s: "" });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const camera_id = form.camera_id || cams.data?.[0]?.camera_id;
    if (!camera_id) return;
    inject.mutate({ camera_id, fault: form.fault, severity: form.severity, ...(form.duration_s ? { duration_s: Number(form.duration_s) } : {}) });
  };

  return (
    <div className="space-y-6">
      <div>
        <span className="micro">Console · admin</span>
        <h1 className="h-page mt-1">Demo control</h1>
        <p className="mt-2 max-w-2xl text-sm muted">Drives the camera simulator. Injected faults are invisible to the scanner except through the images it sees.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Card title="Scenarios" hint="A scenario schedules a scripted sequence of faults across the fleet.">
          {scenarios.error && <ErrorNote error={scenarios.error} />}
          {!scenarios.data && !scenarios.error && <Skeleton className="h-24 w-full" />}
          <ul className="space-y-2.5">
            {scenarios.data?.map((s, i) => (
              <li key={s} className={`flex items-center justify-between gap-3 rounded-[10px] px-4 py-3 ${i === 0 ? "bg-mint" : "bg-tint"}`}>
                <div className="min-w-0">
                  <div className="font-semibold text-ink">{s}</div>
                  <div className="mono text-[11px] muted">scenarios/{s}.yaml</div>
                </div>
                <button className="btn primary sm" disabled={run.isPending} onClick={() => run.mutate(s)} aria-label={`Start scenario ${s}`}>
                  <Icon name="play" size={12} /> Start
                </button>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Inject a fault">
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
            <label className="grid gap-1.5"><span className="micro">Camera</span>
              <select className="field" value={form.camera_id || cams.data?.[0]?.camera_id || ""} onChange={(e) => setForm({ ...form, camera_id: e.target.value })}>
                {cams.data?.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {c.site}</option>)}
              </select>
            </label>
            <label className="grid gap-1.5"><span className="micro">Fault</span>
              <select className="field" value={form.fault} onChange={(e) => setForm({ ...form, fault: e.target.value })}>
                {FAULTS.map((f) => <option key={f} value={f}>{human(f)}</option>)}
              </select>
            </label>
            <label className="grid gap-1.5">
              <span className="flex items-baseline justify-between"><span className="micro">Severity</span><span className="text-sm text-ink"><b className="big-num text-lg">{form.severity}</b> / 5 · {SEV_WORD[form.severity]}</span></span>
              <input type="range" className="slider" min={1} max={5} value={form.severity} onChange={(e) => setForm({ ...form, severity: +e.target.value })}
                aria-valuetext={`${form.severity} of 5, ${SEV_WORD[form.severity]}`} />
            </label>
            <label className="grid gap-1.5"><span className="micro">Duration, seconds (optional)</span>
              <input className="field" type="number" min={1} inputMode="numeric" value={form.duration_s} placeholder="until repaired"
                onChange={(e) => setForm({ ...form, duration_s: e.target.value })} />
            </label>
            <button type="submit" className="btn primary sm:col-span-2" disabled={inject.isPending || !cams.data?.length}>
              {inject.isPending ? <><Icon name="refresh" className="spin" /> Injecting…</> : <><Icon name="bolt" /> Inject fault</>}
            </button>
          </form>
        </Card>
      </div>
    </div>
  );
}
