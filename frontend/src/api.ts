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
