import { useState } from "react";

import ReportForm from "./components/ReportForm";

export default function App() {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  return (
    <main className="console">
      <header>
        <h1>Mission Control</h1>
        <p className="subtitle">Go/No-Go Launch Console</p>
      </header>
      <section className="panel" aria-labelledby="file-heading">
        <h2 id="file-heading">File an anomaly report</h2>
        <ReportForm onFiled={setSelectedId} />
      </section>
      {selectedId !== null && (
        <section className="panel" aria-live="polite">
          <p>Report #{selectedId} filed. Processing…</p>
        </section>
      )}
    </main>
  );
}
