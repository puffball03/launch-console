import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { ReportSummary } from "../api";
import ReportList, { countdown, sortReports } from "../components/ReportList";

const NOW = new Date("2026-11-12T09:00:00Z");

function report(over: Partial<ReportSummary>): ReportSummary {
  return {
    id: 1,
    engineer_name: "Ada",
    station: "WX",
    status: "ready",
    verdict: "go",
    subsystem: "weather",
    effective_severity: "low",
    brief_by_at: "2026-11-12T09:30:00Z",
    flagged: false,
    briefing_status: "pending",
    created_at: "2026-11-12T08:50:00Z",
    ...over,
  };
}

test("processing first, then pending by soonest deadline, then decided newest first", () => {
  const reports = [
    report({ id: 1, briefing_status: "approved", created_at: "2026-11-12T08:00:00Z" }),
    report({ id: 2, brief_by_at: "2026-11-12T09:15:00Z" }),
    report({ id: 3, status: "processing", verdict: null, brief_by_at: null, briefing_status: null }),
    report({ id: 4, brief_by_at: "2026-11-12T09:05:00Z" }),
    report({ id: 5, status: "briefing_failed", briefing_status: null, created_at: "2026-11-12T08:30:00Z" }),
  ];

  expect(sortReports(reports).map((r) => r.id)).toEqual([3, 4, 2, 5, 1]);
});

test("countdown shows time left, or how overdue", () => {
  expect(countdown("2026-11-12T09:04:30Z", NOW)).toBe("4:30 left");
  expect(countdown("2026-11-12T08:59:30Z", NOW)).toBe("Overdue 0:30");
  expect(countdown("2026-11-12T10:00:00Z", NOW)).toBe("60:00 left");
});

test("rows show a GO / NO-GO chip, a flag when flagged, and the countdown", () => {
  render(
    <ReportList
      reports={[
        report({ id: 1, verdict: "no_go", flagged: true, brief_by_at: "2026-11-12T09:04:30Z" }),
        report({ id: 2, verdict: "go", flagged: false }),
      ]}
      selectedId={null}
      onSelect={() => {}}
      now={NOW}
    />,
  );

  const [first, second] = screen.getAllByRole("button");
  expect(within(first).getByText("NO-GO")).toBeInTheDocument();
  expect(within(first).getByLabelText("Flagged for review")).toBeInTheDocument();
  expect(within(first).getByText("4:30 left")).toBeInTheDocument();
  expect(within(second).getByText("GO")).toBeInTheDocument();
  expect(within(second).queryByLabelText("Flagged for review")).not.toBeInTheDocument();
});

test("processing and decided rows say so instead of a countdown", () => {
  render(
    <ReportList
      reports={[
        report({ id: 1, status: "processing", verdict: null, brief_by_at: null, briefing_status: null }),
        report({ id: 2, briefing_status: "approved" }),
        report({ id: 3, briefing_status: "rejected" }),
        report({ id: 4, status: "briefing_failed", briefing_status: null }),
      ]}
      selectedId={null}
      onSelect={() => {}}
      now={NOW}
    />,
  );

  expect(screen.getByText("Processing…")).toBeInTheDocument();
  expect(screen.getByText("Approved")).toBeInTheDocument();
  expect(screen.getByText("Rejected")).toBeInTheDocument();
  expect(screen.getByText("Briefing failed")).toBeInTheDocument();
});

test("clicking a row selects it", async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();
  render(<ReportList reports={[report({ id: 7 })]} selectedId={null} onSelect={onSelect} now={NOW} />);

  await user.click(screen.getByRole("button"));

  expect(onSelect).toHaveBeenCalledWith(7);
});

test("the selected row is marked current", () => {
  render(
    <ReportList reports={[report({ id: 7 }), report({ id: 8 })]} selectedId={8} onSelect={() => {}} now={NOW} />,
  );

  const [, eight] = screen.getAllByRole("button");
  expect(eight).toHaveAttribute("aria-current", "true");
});

test("an empty list says there are no reports", () => {
  render(<ReportList reports={[]} selectedId={null} onSelect={() => {}} now={NOW} />);

  expect(screen.getByText(/no reports yet/i)).toBeInTheDocument();
});


test("a pending report without a deadline sorts after those with one", () => {
  const reports = [
    report({ id: 1, brief_by_at: null }),
    report({ id: 2, brief_by_at: "2026-11-12T09:15:00Z" }),
    report({ id: 3, brief_by_at: "2026-11-12T09:05:00Z" }),
  ];

  expect(sortReports(reports).map((r) => r.id)).toEqual([3, 2, 1]);
});
