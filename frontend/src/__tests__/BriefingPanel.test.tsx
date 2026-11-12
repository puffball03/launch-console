import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Briefing } from "../api";
import BriefingPanel from "../components/BriefingPanel";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

function briefing(over: Partial<Briefing> = {}): Briefing {
  return {
    id: 11,
    status: "pending",
    headline: "NO-GO: wind over limit at the tower",
    situation: "Gusts reached 30 kt for two minutes.",
    impact_on_launch: "Launch cannot proceed.",
    recommended_action: "Hold and re-check in 15 minutes.",
    open_questions: ["Is the trend rising?", "Completeness check: No time of the gust peak."],
    verdict: "no_go",
    violations: [{ field: "wind_knots", value: 30, limit: "<= 25" }],
    brief_by_minutes: 5,
    brief_by_at: "2026-11-12T09:05:00Z",
    rounds: 1,
    reviewer_satisfied: true,
    final_feedback: "Clear.",
    decided_by: null,
    decided_at: null,
    reject_reason: null,
    ...over,
  };
}

function respond(status: number, body: unknown) {
  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify(body), { status }));
}

test("shows the drafted briefing and its open questions", () => {
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  expect(screen.getByRole("heading", { name: "NO-GO: wind over limit at the tower" })).toBeInTheDocument();
  expect(screen.getByText("Gusts reached 30 kt for two minutes.")).toBeInTheDocument();
  expect(screen.getByText("Launch cannot proceed.")).toBeInTheDocument();
  expect(screen.getByText("Hold and re-check in 15 minutes.")).toBeInTheDocument();
  expect(screen.getByText("Completeness check: No time of the gust peak.")).toBeInTheDocument();
});

test("a reviewer-not-satisfied tag shows the final feedback", () => {
  render(
    <BriefingPanel
      briefing={briefing({ reviewer_satisfied: false, rounds: 3, final_feedback: "Still missing the trend." })}
      reportReady
      onDecided={() => {}}
    />,
  );

  expect(screen.getByText("Reviewer not satisfied")).toBeInTheDocument();
  expect(screen.getByText(/Still missing the trend\./)).toBeInTheDocument();
});

test("no tag when the reviewer passed it", () => {
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  expect(screen.queryByText("Reviewer not satisfied")).not.toBeInTheDocument();
});

test("approve and reject stay disabled until an approver name is typed", async () => {
  const user = userEvent.setup();
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  const approve = screen.getByRole("button", { name: "Approve" });
  const reject = screen.getByRole("button", { name: "Reject" });
  expect(approve).toBeDisabled();
  expect(reject).toBeDisabled();

  await user.type(screen.getByLabelText(/approver name/i), "   ");
  expect(approve).toBeDisabled();

  await user.type(screen.getByLabelText(/approver name/i), "Kim");
  expect(approve).toBeEnabled();
  expect(reject).toBeEnabled();
});

test("approve sends the name and reports the decided briefing", async () => {
  const user = userEvent.setup();
  const onDecided = vi.fn();
  const approved = briefing({ status: "approved", decided_by: "Kim", decided_at: "2026-11-12T09:02:00Z" });
  respond(200, approved);
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={onDecided} />);

  await user.type(screen.getByLabelText(/approver name/i), "Kim");
  await user.click(screen.getByRole("button", { name: "Approve" }));

  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/briefings/11/approve");
  expect(JSON.parse(init.body)).toEqual({ approver_name: "Kim" });
  expect(onDecided).toHaveBeenCalledWith(approved);
});

test("reject sends the optional reason", async () => {
  const user = userEvent.setup();
  respond(200, briefing({ status: "rejected", decided_by: "Kim", reject_reason: "Need the trend." }));
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  await user.type(screen.getByLabelText(/approver name/i), "Kim");
  await user.type(screen.getByLabelText(/reason/i), "Need the trend.");
  await user.click(screen.getByRole("button", { name: "Reject" }));

  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/briefings/11/reject");
  expect(JSON.parse(init.body)).toEqual({ approver_name: "Kim", reason: "Need the trend." });
});

test("a refused decision shows the server's message and keeps the controls", async () => {
  const user = userEvent.setup();
  respond(409, { detail: "Already approved by Lee." });
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  await user.type(screen.getByLabelText(/approver name/i), "Kim");
  await user.click(screen.getByRole("button", { name: "Approve" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Already approved by Lee.");
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
});

test("a decided briefing shows who decided and no buttons", () => {
  render(
    <BriefingPanel
      briefing={briefing({ status: "rejected", decided_by: "Kim", decided_at: "2026-11-12T09:02:00Z", reject_reason: "Need the trend." })}
      reportReady
      onDecided={() => {}}
    />,
  );

  expect(screen.getByText(/Rejected by Kim/)).toBeInTheDocument();
  expect(screen.getByText(/Need the trend\./)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
});

test("no decision controls while the report is not ready", () => {
  render(<BriefingPanel briefing={briefing()} reportReady={false} onDecided={() => {}} />);

  expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
});


test("the reason box is labelled as applying to a rejection only", () => {
  render(<BriefingPanel briefing={briefing()} reportReady onDecided={() => {}} />);

  expect(screen.getByLabelText("Reason for rejection (optional)")).toBeInTheDocument();
  expect(screen.getByText(/approving ignores this box/i)).toBeInTheDocument();
});
