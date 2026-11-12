import type { TraceStep } from "../api";

type Props = {
  trace: TraceStep[];
  totalCostUsd: string;
};

function TraceCard({ step }: { step: TraceStep }) {
  return (
    <li className={`trace-card trace-${step.status}`}>
      <div className="trace-head">
        <h4>{step.step}</h4>
        <span className="badge">{step.kind === "code" ? "code" : step.model}</span>
        <span className={`trace-status status-${step.status}`}>{step.status}</span>
      </div>
      <div className="trace-numbers">
        <span>
          {step.input_tokens} in / {step.output_tokens} out
        </span>
        <span>${step.cost_usd}</span>
        <span>{step.duration_ms} ms</span>
      </div>
      {step.error && <p className="trace-error-text">{step.error}</p>}
      {(step.input_preview || step.output_preview) && (
        <details>
          <summary>Input and output</summary>
          {step.input_preview && <pre className="preview">{step.input_preview}</pre>}
          {step.output_preview && <pre className="preview">{step.output_preview}</pre>}
        </details>
      )}
    </li>
  );
}

export default function TracePanel({ trace, totalCostUsd }: Props) {
  return (
    <section className="trace" aria-label="Trace">
      {/* The total is calculated in code on the server; shown as sent, never recalculated here. */}
      <h3>
        Trace <span className="trace-total">Total cost ${totalCostUsd}</span>
      </h3>
      {trace.length === 0 ? (
        <p className="muted">No steps have run yet.</p>
      ) : (
        <ol className="trace-list">
          {trace.map((step) => (
            <TraceCard key={step.seq} step={step} />
          ))}
        </ol>
      )}
    </section>
  );
}
