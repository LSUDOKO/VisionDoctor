import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { api, post, type Camera } from "../api";
import { ErrorNote, Section } from "../ui";

const FAULTS = ["drift", "vibration", "haze", "condensation", "glare", "exposure", "color_cast", "ir_cut_stuck", "noise",
  "occlusion", "smudge", "spider_web", "defocus", "freeze", "dead"];

function Result({ m }: { m: { data?: unknown; error: unknown } }) {
  if (m.error) return <ErrorNote error={m.error} />;
  if (m.data === undefined) return null;
  return <pre role="status" className="mt-3 overflow-x-auto rounded-md bg-raised p-2 font-mono text-xs">{JSON.stringify(m.data, null, 2)}</pre>;
}

export default function Demo() {
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<string[]>("/api/scenarios") });
  const cams = useQuery({ queryKey: ["cameras"], queryFn: () => api<Camera[]>("/api/cameras") });
  const run = useMutation({ mutationFn: (name: string) => post("/api/sim/scenario", { name }) });
  const inject = useMutation({ mutationFn: (b: Record<string, unknown>) => post("/api/sim/inject", b) });
  const [form, setForm] = useState({ camera_id: "", fault: "haze", severity: 3, duration_s: "" });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const camera_id = form.camera_id || cams.data?.[0]?.camera_id;
    if (!camera_id) return;
    inject.mutate({ camera_id, fault: form.fault, severity: form.severity, ...(form.duration_s ? { duration_s: Number(form.duration_s) } : {}) });
  };

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold">Demo control</h2>
        <p className="text-sm text-muted">Admin only. Drives the camera simulator for live judging; faults are invisible to the scanner except through the images.</p>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Scenarios">
          {scenarios.error && <ErrorNote error={scenarios.error} />}
          <ul className="space-y-2">
            {scenarios.data?.map((s) => (
              <li key={s} className="flex items-center justify-between rounded-md border border-line px-3 py-2">
                <span className="font-mono text-sm">{s}.yaml</span>
                <button className="btn btn-primary" disabled={run.isPending} onClick={() => run.mutate(s)}>▶ Start</button>
              </li>
            ))}
          </ul>
          <Result m={run} />
        </Section>
        <Section title="Inject a fault">
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1 text-sm">Camera
              <select className="field" value={form.camera_id} onChange={(e) => setForm({ ...form, camera_id: e.target.value })}>
                {cams.data?.map((c) => <option key={c.camera_id} value={c.camera_id}>{c.camera_id} · {c.site}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm">Fault
              <select className="field" value={form.fault} onChange={(e) => setForm({ ...form, fault: e.target.value })}>
                {FAULTS.map((f) => <option key={f}>{f}</option>)}
              </select>
            </label>
            <label className="grid gap-1 text-sm" title="1 = barely visible, 5 = severe"><span>Severity: <span className="num">{form.severity}</span> / 5</span>
              <input type="range" min={1} max={5} value={form.severity} onChange={(e) => setForm({ ...form, severity: +e.target.value })} className="accent-[rgb(var(--accent))]" />
            </label>
            <label className="grid gap-1 text-sm" title="Leave empty for a fault that stays until repaired">Duration (s, optional)
              <input className="field" type="number" min={1} inputMode="numeric" value={form.duration_s} placeholder="until repaired"
                onChange={(e) => setForm({ ...form, duration_s: e.target.value })} />
            </label>
            <button type="submit" className="btn btn-primary sm:col-span-2 justify-center" disabled={inject.isPending || !cams.data?.length}>Inject fault</button>
          </form>
          <Result m={inject} />
        </Section>
      </div>
    </div>
  );
}
