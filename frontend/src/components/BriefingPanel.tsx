import { useState } from "react";

import { type Briefing, decideBriefing } from "../api";

type Props = {
  briefing: Briefing;
  reportReady: boolean;
  onDecided: (briefing: Briefing) => void;
  /** Called when the server refused because the briefing changed elsewhere (409). */
  onStale?: () => void;
};

function Decision({ briefing }: { briefing: Briefing }) {
  const word = briefing.status === "approved" ? "Approved" : "Rejected";
  const when = briefing.decided_at ? new Date(briefing.decided_at).toLocaleTimeString() : "";
  return (
    <p className={`decision decision-${briefing.status}`}>
      {word} by {briefing.decided_by} {when && `at ${when}`}
      {briefing.reject_reason && <span className="reject-reason"> — {briefing.reject_reason}</span>}
    </p>
  );
}

export default function BriefingPanel({ briefing, reportReady, onDecided, onStale }: Props) {
  const [approver, setApprover] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const canDecide = approver.trim().length > 0 && !sending;

  async function decide(action: "approve" | "reject") {
    setSending(true);
    setError(null);
    const result = await decideBriefing(briefing.id, action, approver.trim(), action === "reject" ? reason.trim() : undefined);
    setSending(false);
    if (result.ok) {
      onDecided(result.briefing);
      return;
    }
    setError(result.message);
    if (result.conflict) onStale?.();
  }

  return (
    <article className="briefing">
      <h3>{briefing.headline}</h3>
      {!briefing.reviewer_satisfied && (
        <p className="tag tag-warn">
          <strong>Reviewer not satisfied</strong> after {briefing.rounds} round{briefing.rounds === 1 ? "" : "s"}
          {briefing.final_feedback && `: ${briefing.final_feedback}`}
        </p>
      )}
      <dl className="briefing-body">
        <dt>Situation</dt>
        <dd>{briefing.situation}</dd>
        <dt>Impact on launch</dt>
        <dd>{briefing.impact_on_launch}</dd>
        <dt>Recommended action</dt>
        <dd>{briefing.recommended_action}</dd>
      </dl>
      {briefing.open_questions.length > 0 && (
        <>
          <h4>Open questions</h4>
          <ul>
            {briefing.open_questions.map((q, i) => (
              <li key={`${i}-${q}`}>{q}</li>
            ))}
          </ul>
        </>
      )}

      {briefing.status !== "pending" ? (
        <Decision briefing={briefing} />
      ) : (
        reportReady && (
          <div className="decide">
            <label htmlFor="approver">Approver name</label>
            <input id="approver" value={approver} onChange={(e) => setApprover(e.target.value)} />
            <label htmlFor="reason">Reason for rejection (optional)</label>
            <input
              id="reason"
              aria-describedby="reason-hint"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <p id="reason-hint" className="muted hint">
              Sent only with Reject; approving ignores this box.
            </p>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <div className="decide-buttons">
              <button type="button" className="approve" disabled={!canDecide} onClick={() => decide("approve")}>
                Approve
              </button>
              <button type="button" className="reject" disabled={!canDecide} onClick={() => decide("reject")}>
                Reject
              </button>
            </div>
          </div>
        )
      )}
    </article>
  );
}
