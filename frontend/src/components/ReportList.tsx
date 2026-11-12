import type { ReportSummary } from "../api";

type Props = {
  reports: ReportSummary[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  now: Date;
};

function rank(r: ReportSummary): number {
  if (r.status === "processing") return 0;
  if (r.briefing_status === "pending" && r.status === "ready") return 1;
  return 2;
}

function deadline(r: ReportSummary): number {
  return r.brief_by_at ? Date.parse(r.brief_by_at) : Number.POSITIVE_INFINITY;
}

/** Processing first, then pending briefings by soonest deadline, then decided or failed, newest first. */
export function sortReports(reports: ReportSummary[]): ReportSummary[] {
  return [...reports].sort((a, b) => {
    const byRank = rank(a) - rank(b);
    if (byRank !== 0) return byRank;
    if (rank(a) === 1) return deadline(a) - deadline(b) || 0; // two missing deadlines: Infinity - Infinity is NaN
    return Date.parse(b.created_at) - Date.parse(a.created_at);
  });
}

export function countdown(briefByAt: string, now: Date): string {
  const seconds = Math.round((Date.parse(briefByAt) - now.getTime()) / 1000);
  const abs = Math.abs(seconds);
  const clock = `${Math.floor(abs / 60)}:${String(abs % 60).padStart(2, "0")}`;
  return seconds >= 0 ? `${clock} left` : `Overdue ${clock}`;
}

function whenLabel(r: ReportSummary, now: Date): string {
  if (r.status === "processing") return "Processing…";
  if (r.status === "briefing_failed") return "Briefing failed";
  if (r.status === "failed") return "Pipeline failed";
  if (r.briefing_status === "approved") return "Approved";
  if (r.briefing_status === "rejected") return "Rejected";
  return r.brief_by_at ? countdown(r.brief_by_at, now) : "";
}

export function VerdictChip({ verdict }: { verdict: ReportSummary["verdict"] }) {
  if (verdict === null) return <span className="chip chip-pending">…</span>;
  return verdict === "go" ? <span className="chip chip-go">GO</span> : <span className="chip chip-no-go">NO-GO</span>;
}

export default function ReportList({ reports, selectedId, onSelect, now }: Props) {
  if (reports.length === 0) return <p className="muted">No reports yet. File one above.</p>;

  return (
    <ul className="report-list">
      {sortReports(reports).map((r) => {
        const when = whenLabel(r, now);
        return (
          <li key={r.id}>
            <button
              type="button"
              className="report-row"
              aria-current={r.id === selectedId ? "true" : undefined}
              onClick={() => onSelect(r.id)}
            >
              <VerdictChip verdict={r.verdict} />
              {r.flagged && (
                <span className="flag" aria-label="Flagged for review" title="Flagged for review">
                  ⚑
                </span>
              )}
              <span className="row-main">
                #{r.id} {r.station} · {r.subsystem ?? "sorting…"} · {r.effective_severity ?? "—"}
              </span>
              <span className={when.startsWith("Overdue") ? "row-when overdue" : "row-when"}>{when}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
