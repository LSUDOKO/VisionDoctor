export type Status = "healthy" | "watch" | "degraded" | "failed" | "repairing";

export interface Camera {
  camera_id: string; name: string; site: string; criticality: number; status: Status;
  last_scan_at?: number; overall_score?: number; predicted_ai_accuracy?: number | null;
  top_faults?: unknown[]; corrections?: unknown[]; thumbnail_url?: string;
}
export interface Check { name?: string; score: number; severity: number; evidence?: Record<string, unknown> }
export interface Report {
  ts: number; overall_score: number; checks: Record<string, Check>; heatmap?: number[][]; scan_ms?: number;
  predicted_ai_accuracy?: number | null; predicted_drop?: number | null;
}
export interface Correction { repair_id: string; type: string; params?: Record<string, unknown> }
export interface CameraDetail extends Camera {
  latest_report: Report | null;
  images: { current?: string; heatmap?: string; reference?: string };
  corrections: Correction[];
  open_incident: Incident | null;
  active_sim_faults: { fault: string; severity: number; event_id?: string }[];
}
export interface HistoryRow { ts: number; overall: number; predicted_ai_accuracy: number | null; severities: Record<string, number> }
export interface Approval { approval_id: string; state: string; action?: string; reason?: string; decided_by?: string }
export interface Incident {
  incident_id: string; camera_id: string; opened_at: number; fault_types?: string[]; severities?: Record<string, number> | number[];
  priority_score?: number; predicted_drop?: number | null; criticality?: number; state: string;
  repairs?: Record<string, unknown>[]; vlm_description?: string | null; evidence_urls?: string[];
  approval?: Approval | null; trace_id?: string | null; ticket_id?: string | null;
}
export interface TraceStep {
  i: number; tool: string; input?: Record<string, unknown>; output_summary: string; decision_reason?: string;
  latency_ms: number; guard: string; changed_plan?: boolean;
}
export interface Trace {
  trace_id: string; incident_id: string; camera_id: string; agent: string; model?: string | null; steps: TraceStep[];
  outcome: string; started: number; total_ms: number; tokens_in?: number; tokens_out?: number;
}
export interface Summary {
  cameras: number; healthy_pct: number; by_status: Record<Status, number>; predicted_fleet_accuracy: number | null;
  open_incidents: number; awaiting_approval: number; auto_fixed_today: number; false_alarms_today: number; is_cool: boolean;
}
export type OpMetrics = Record<string, { n: number; p50_ms: number; p95_ms: number }>;

export const tokenKey = "vd_token";

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const token = localStorage.getItem(tokenKey);
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method: body === undefined ? "GET" : "POST", headers, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* non-JSON error */ }
    throw new Error(`${res.status} ${typeof detail === "string" ? detail : JSON.stringify(detail)}`);
  }
  return res.json() as Promise<T>;
}

export const post = <T = unknown>(path: string, body: unknown = {}) => api<T>(path, body);
