import { useCallback, useEffect, useState } from "react";

import {
  type Briefing,
  getHealth,
  getReport,
  listReports,
  type ReportDetail as Detail,
  type ReportSummary,
} from "./api";
import ReportDetail from "./components/ReportDetail";
import ReportForm from "./components/ReportForm";
import ReportList from "./components/ReportList";

const POLL_MS = 2000;

export default function App() {
  const [provider, setProvider] = useState<string | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [now, setNow] = useState(() => new Date());

  const refresh = useCallback(async () => {
    try {
      setReports(await listReports());
      if (selectedId !== null) setDetail(await getReport(selectedId));
    } catch {
      // Keep what is on screen; the next poll or action tries again.
    }
  }, [selectedId]);

  useEffect(() => {
    getHealth()
      .then((h) => setProvider(h.provider))
      .catch(() => setProvider(null));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll only while something is still being processed.
  const processing = reports.some((r) => r.status === "processing") || detail?.status === "processing";
  useEffect(() => {
    if (!processing) return;
    const timer = setTimeout(refresh, POLL_MS);
    return () => clearTimeout(timer);
  }, [processing, refresh, reports, detail]);

  // A one-second clock drives the countdowns.
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  function onDecided(briefing: Briefing) {
    // A decision can land after the user has switched reports: only merge it into its own report.
    setDetail((d) => (d && d.briefing?.id === briefing.id ? { ...d, briefing, briefing_status: briefing.status } : d));
    listReports()
      .then(setReports)
      .catch(() => {});
  }

  return (
    <main className="console">
      <header className="console-header">
        <div>
          <h1>Mission Control</h1>
          <p className="subtitle">Go/No-Go Launch Console</p>
        </div>
        {provider === "fake" && (
          <span className="badge badge-fake" title="No API key set: model steps use the built-in fake">
            FAKE MODEL
          </span>
        )}
      </header>
      <section className="panel" aria-labelledby="file-heading">
        <h2 id="file-heading">File an anomaly report</h2>
        <ReportForm onFiled={setSelectedId} />
      </section>
      <div className="console-grid">
        <section className="panel" aria-labelledby="reports-heading">
          <h2 id="reports-heading">Reports</h2>
          <ReportList reports={reports} selectedId={selectedId} onSelect={setSelectedId} now={now} />
        </section>
        <section className="panel" aria-live="polite" aria-label="Selected report">
          {detail && detail.id === selectedId ? (
            <ReportDetail report={detail} now={now} onDecided={onDecided} />
          ) : (
            <p className="muted">Select a report to see its briefing.</p>
          )}
        </section>
      </div>
    </main>
  );
}
