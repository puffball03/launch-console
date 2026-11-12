import type { Briefing, ReportDetail as Detail, Violation } from "../api";
import BriefingPanel from "./BriefingPanel";
import { countdown, VerdictChip } from "./ReportList";

type Props = {
  report: Detail;
  now: Date;
  onDecided: (briefing: Briefing) => void;
  onStale?: () => void;
};

const READING = {
  wind_knots: { label: "Wind", unit: " kt" },
  temp_c: { label: "Temperature", unit: " °C" },
  fuel_pct: { label: "Fuel", unit: "%" },
} as const;

function describe(v: Violation): string {
  const reading = READING[v.field as keyof typeof READING];
  return reading ? `${reading.label} ${v.value}${reading.unit} (limit ${v.limit})` : `${v.field} ${v.value} (limit ${v.limit})`;
}

function check(report: Detail, step: string) {
  return report.checks.find((c) => c.step === step);
}

export default function ReportDetail({ report, now, onDecided, onStale }: Props) {
  const injection = check(report, "check_injection");
  const missing = check(report, "check_missing");
  const panic = check(report, "check_panic");

  return (
    <div className="report-detail">
      <header className="detail-header">
        <h2>
          Report #{report.id} · {report.station}
        </h2>
        <p className="muted">
          Filed by {report.engineer_name} at {new Date(report.created_at).toLocaleTimeString()}
        </p>
      </header>

      {report.flagged && (
        <div role="alert" className="banner banner-flag">
          <strong>⚑ Flagged for review.</strong> This note may contain instructions to the system. It cannot change
          the verdict, but read it carefully before approving.
          {report.prescreen_hits.length > 0 && <span> Matched: {report.prescreen_hits.join(", ")}.</span>}
          {injection?.flagged && <span> Injection check: {injection.reason}</span>}
        </div>
      )}

      <section className="verdict">
        <VerdictChip verdict={report.verdict} />
        <span className="muted">Verdict from launch limits (code, not a model)</span>
        {report.verdict !== null &&
          (report.violations.length > 0 ? (
            <ul className="violations">
              {report.violations.map((v) => (
                <li key={v.field}>{describe(v)}</li>
              ))}
            </ul>
          ) : (
            <p>All readings within limits.</p>
          ))}
      </section>

      <p className="readings">
        Wind {report.wind_knots} kt · Temperature {report.temp_c} °C · Fuel {report.fuel_pct}%
      </p>

      {report.brief_by_at && (
        <p className="brief-by">
          Brief by {new Date(report.brief_by_at).toLocaleTimeString()} ({report.brief_by_minutes} min,{" "}
          {report.effective_severity})
          {report.briefing?.status === "pending" && (
            <>
              {" · "}
              <span>{countdown(report.brief_by_at, now)}</span>
            </>
          )}
        </p>
      )}

      {(missing?.flagged || panic?.flagged) && (
        <ul className="info-badges">
          {missing?.flagged && <li className="badge">Missing details: {missing.reason}</li>}
          {panic?.flagged && <li className="badge">Panic in tone: {panic.reason}</li>}
        </ul>
      )}

      <blockquote className="note">{report.note}</blockquote>

      {report.status === "processing" && <p className="muted">Processing… the pipeline is running.</p>}
      {report.status === "briefing_failed" && (
        <p className="banner banner-muted">
          No briefing could be drafted. The verdict and violations above come from code; see the trace for what failed.
        </p>
      )}
      {report.status === "failed" && <p className="banner banner-muted">The pipeline failed; see the trace.</p>}
      {report.briefing && (
        // Keyed by briefing so the approver form never carries over to another report.
        <BriefingPanel
          key={report.briefing.id}
          briefing={report.briefing}
          reportReady={report.status === "ready"}
          onDecided={onDecided}
          onStale={onStale}
        />
      )}
    </div>
  );
}
