export const STATIONS = ["PROP", "GNC", "TELEM", "RANGE", "WX"] as const;
export type Station = (typeof STATIONS)[number];

export type ReportInput = {
  engineer_name: string;
  station: Station;
  wind_knots: number;
  temp_c: number;
  fuel_pct: number;
  note: string;
};

export type FieldErrors = Partial<Record<keyof ReportInput | "_body", string>>;

export type FileResult =
  | { ok: true; id: number; status: string }
  | { ok: false; errors: FieldErrors };

export async function fileReport(report: ReportInput): Promise<FileResult> {
  const response = await fetch("/api/reports", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(report),
  });
  if (response.ok) {
    const body = await response.json();
    return { ok: true, id: body.id, status: body.status };
  }
  // A proxy or crash can return text or HTML; only a rejected fetch means "could not reach".
  const body = await response.json().catch(() => null);
  const errors: FieldErrors = body?.errors ?? {};
  if (Object.keys(errors).length === 0) {
    const detail = typeof body?.detail === "string" ? body.detail : null;
    errors._body = detail ?? `Server error (${response.status}).`;
  }
  return { ok: false, errors };
}

export type Violation = { field: string; value: number; limit: string };
export type ReportStatus = "processing" | "ready" | "briefing_failed" | "failed";
export type BriefingStatus = "pending" | "approved" | "rejected";

export type ReportSummary = {
  id: number;
  engineer_name: string;
  station: Station;
  status: ReportStatus;
  verdict: "go" | "no_go" | null;
  subsystem: string | null;
  effective_severity: "high" | "medium" | "low" | null;
  brief_by_at: string | null;
  flagged: boolean | null;
  briefing_status: BriefingStatus | null;
  created_at: string;
};

export type Briefing = {
  id: number;
  status: BriefingStatus;
  headline: string;
  situation: string;
  impact_on_launch: string;
  recommended_action: string;
  open_questions: string[];
  verdict: "go" | "no_go";
  violations: Violation[];
  brief_by_minutes: number;
  brief_by_at: string;
  rounds: number;
  reviewer_satisfied: boolean;
  final_feedback: string | null;
  decided_by: string | null;
  decided_at: string | null;
  reject_reason: string | null;
};

export type DecisionResult = { ok: true; briefing: Briefing } | { ok: false; message: string; conflict: boolean };

export async function decideBriefing(
  briefingId: number,
  action: "approve" | "reject",
  approverName: string,
  reason?: string,
): Promise<DecisionResult> {
  let response: Response;
  try {
    response = await fetch(`/api/briefings/${briefingId}/${action}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(reason ? { approver_name: approverName, reason } : { approver_name: approverName }),
    });
  } catch {
    return { ok: false, message: "Could not reach the server. Try again.", conflict: false };
  }
  const body = await response.json().catch(() => null);
  if (response.ok) return { ok: true, briefing: body };
  const fieldMessage = body?.errors ? Object.values(body.errors)[0] : null;
  const message = fieldMessage ?? body?.detail ?? `Server error (${response.status}).`;
  return { ok: false, message: String(message), conflict: response.status === 409 };
}

export type CheckSummary = { step: string; flagged: boolean; reason: string; status: string };

export type ReportDetail = ReportSummary & {
  note: string;
  wind_knots: number;
  temp_c: number;
  fuel_pct: number;
  violations: Violation[];
  checks: CheckSummary[];
  prescreen_hits: string[];
  brief_by_minutes: number | null;
  briefing: Briefing | null;
  total_cost_usd: string;
};

export type Health = { ok: boolean; provider: "fake" | "foundry" };

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  return response.json();
}

export const listReports = () => getJson<ReportSummary[]>("/api/reports");
export const getReport = (id: number) => getJson<ReportDetail>(`/api/reports/${id}`);
export const getHealth = () => getJson<Health>("/api/health");
