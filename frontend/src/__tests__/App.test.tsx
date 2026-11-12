import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Briefing, ReportDetail, ReportSummary } from "../api";
import App from "../App";

const BRIEFING: Briefing = {
  id: 11, status: "pending", headline: "NO-GO: wind over limit", situation: "Gusts hit 30 kt.",
  impact_on_launch: "Hold.", recommended_action: "Re-check.", open_questions: [], verdict: "no_go",
  violations: [], brief_by_minutes: 5, brief_by_at: "2030-01-01T00:05:00Z", rounds: 1,
  reviewer_satisfied: true, final_feedback: null, decided_by: null, decided_at: null, reject_reason: null,
};

function summary(over: Partial<ReportSummary> = {}): ReportSummary {
  return {
    id: 4, engineer_name: "Ada", station: "WX", status: "ready", verdict: "no_go", subsystem: "weather",
    effective_severity: "high", brief_by_at: "2030-01-01T00:05:00Z", flagged: false, briefing_status: "pending",
    created_at: "2030-01-01T00:00:00Z", ...over,
  };
}

function detail(over: Partial<ReportDetail> = {}): ReportDetail {
  return {
    ...summary(), note: "Gusts at the tower.", wind_knots: 30, temp_c: 10, fuel_pct: 99,
    violations: [{ field: "wind_knots", value: 30, limit: "<= 25" }], checks: [], prescreen_hits: [],
    brief_by_minutes: 5, briefing: BRIEFING, trace: [], total_cost_usd: "0.002", ...over,
  };
}

type Server = {
  provider: "fake" | "foundry";
  reports: ReportSummary[];
  details: Record<number, ReportDetail>;
  posted?: { id: number };
  approved?: Briefing;
};

function serve(server: Server) {
  const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url === "/api/health") return json({ ok: true, provider: server.provider });
    if (url === "/api/reports" && init?.method === "POST") return json(server.posted, 201);
    if (url === "/api/reports") return json(server.reports);
    const reportMatch = url.match(/^\/api\/reports\/(\d+)$/);
    if (reportMatch) return json(server.details[Number(reportMatch[1])]);
    if (url.endsWith("/approve")) return json(server.approved);
    return json({ detail: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function listCalls(fetchMock: ReturnType<typeof serve>) {
  return fetchMock.mock.calls.filter(([url, init]) => url === "/api/reports" && !init?.method).length;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

test("renders the Mission Control console heading", () => {
  serve({ provider: "fake", reports: [], details: {} });
  render(<App />);

  expect(screen.getByRole("heading", { name: /mission control/i })).toBeInTheDocument();
});

test("shows a FAKE MODEL badge when the server runs without a key", async () => {
  serve({ provider: "fake", reports: [], details: {} });
  render(<App />);

  expect(await screen.findByText("FAKE MODEL")).toBeInTheDocument();
});

test("no badge on the real model", async () => {
  const fetchMock = serve({ provider: "foundry", reports: [], details: {} });
  render(<App />);

  await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/health"));
  expect(screen.queryByText("FAKE MODEL")).not.toBeInTheDocument();
});

test("lists reports and shows the selected one in detail", async () => {
  const user = userEvent.setup();
  serve({ provider: "fake", reports: [summary()], details: { 4: detail() } });
  render(<App />);

  await user.click(await screen.findByRole("button", { name: /#4 WX/ }));

  expect(await screen.findByRole("heading", { name: "Report #4 · WX" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "NO-GO: wind over limit" })).toBeInTheDocument();
});

test("filing a report selects it", async () => {
  const user = userEvent.setup();
  serve({
    provider: "fake",
    reports: [summary({ id: 42 })],
    details: { 42: detail({ id: 42 }) },
    posted: { id: 42 },
  });
  render(<App />);

  await user.type(screen.getByLabelText(/name/i), "Ada");
  await user.selectOptions(screen.getByLabelText(/station/i), "WX");
  await user.type(screen.getByLabelText(/wind/i), "10");
  await user.type(screen.getByLabelText(/temp/i), "10");
  await user.type(screen.getByLabelText(/fuel/i), "99");
  await user.type(screen.getByLabelText(/note/i), "Gusts rising");
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByRole("heading", { name: "Report #42 · WX" })).toBeInTheDocument();
});

test("polls every 2 s while a report is processing and stops once nothing is", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const server: Server = {
    provider: "fake",
    reports: [summary({ status: "processing", verdict: null, brief_by_at: null, briefing_status: null })],
    details: {},
  };
  const fetchMock = serve(server);
  render(<App />);
  await waitFor(() => expect(listCalls(fetchMock)).toBe(1));

  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(listCalls(fetchMock)).toBe(2);

  server.reports = [summary()];
  await act(() => vi.advanceTimersByTimeAsync(2000));
  expect(listCalls(fetchMock)).toBe(3);

  await act(() => vi.advanceTimersByTimeAsync(6000));
  expect(listCalls(fetchMock)).toBe(3);
});

test("approving updates the detail and the list", async () => {
  const user = userEvent.setup();
  const server: Server = {
    provider: "fake",
    reports: [summary()],
    details: { 4: detail() },
    approved: { ...BRIEFING, status: "approved", decided_by: "Kim", decided_at: "2030-01-01T00:01:00Z" },
  };
  serve(server);
  render(<App />);
  await user.click(await screen.findByRole("button", { name: /#4 WX/ }));
  await user.type(await screen.findByLabelText(/approver name/i), "Kim");

  server.reports = [summary({ briefing_status: "approved" })];
  await user.click(screen.getByRole("button", { name: "Approve" }));

  expect(await screen.findByText(/Approved by Kim/)).toBeInTheDocument();
  const row = screen.getByRole("button", { name: /#4 WX/ });
  await waitFor(() => expect(within(row).getByText("Approved")).toBeInTheDocument());
});


test("a decision that lands after switching reports doesn't change the other report", async () => {
  const user = userEvent.setup();
  const server: Server = {
    provider: "fake",
    reports: [summary({ id: 4 }), summary({ id: 5, station: "PROP" })],
    details: {
      4: detail({ id: 4 }),
      5: detail({ id: 5, station: "PROP", briefing: { ...BRIEFING, id: 12, headline: "GO: all nominal" } }),
    },
  };
  const fetchMock = serve(server);
  let finish: (r: Response) => void = () => {};
  const base = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string, init?: RequestInit) =>
    url.endsWith("/approve") ? new Promise<Response>((resolve) => (finish = resolve)) : base(url, init),
  );
  render(<App />);

  await user.click(await screen.findByRole("button", { name: /#4 WX/ }));
  await user.type(await screen.findByLabelText(/approver name/i), "Kim");
  await user.click(screen.getByRole("button", { name: "Approve" }));
  await user.click(screen.getByRole("button", { name: /#5 PROP/ }));
  expect(await screen.findByRole("heading", { name: "GO: all nominal" })).toBeInTheDocument();

  const approved = { ...BRIEFING, id: 11, status: "approved", decided_by: "Kim", decided_at: "2030-01-01T00:01:00Z" };
  await act(async () => finish(new Response(JSON.stringify(approved), { status: 200 })));

  expect(screen.getByRole("heading", { name: "GO: all nominal" })).toBeInTheDocument();
  expect(screen.queryByText(/Approved by Kim/)).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
});


test("a slow response for the previous selection doesn't replace the current one", async () => {
  const user = userEvent.setup();
  const server: Server = {
    provider: "fake",
    reports: [summary({ id: 4 }), summary({ id: 5, station: "PROP" })],
    details: {
      4: detail({ id: 4 }),
      5: detail({ id: 5, station: "PROP", briefing: { ...BRIEFING, id: 12, headline: "GO: all nominal" } }),
    },
  };
  const fetchMock = serve(server);
  let releaseFour: () => void = () => {};
  const base = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string, init?: RequestInit) =>
    url === "/api/reports/4"
      ? new Promise<Response>((resolve) => (releaseFour = () => resolve(base(url, init) as unknown as Response)))
      : base(url, init),
  );
  render(<App />);

  await user.click(await screen.findByRole("button", { name: /#4 WX/ }));
  await user.click(screen.getByRole("button", { name: /#5 PROP/ }));
  expect(await screen.findByRole("heading", { name: "GO: all nominal" })).toBeInTheDocument();

  await act(async () => releaseFour());

  expect(screen.getByRole("heading", { name: "GO: all nominal" })).toBeInTheDocument();
  expect(screen.queryByText(/select a report/i)).not.toBeInTheDocument();
});


test("if someone else decided first, the refusal reloads the report", async () => {
  const user = userEvent.setup();
  const server: Server = { provider: "fake", reports: [summary()], details: { 4: detail() } };
  const fetchMock = serve(server);
  const base = fetchMock.getMockImplementation()!;
  fetchMock.mockImplementation((url: string, init?: RequestInit) =>
    url.endsWith("/approve")
      ? Promise.resolve(new Response(JSON.stringify({ detail: "Already approved by Lee." }), { status: 409 }))
      : base(url, init),
  );
  render(<App />);
  await user.click(await screen.findByRole("button", { name: /#4 WX/ }));
  await user.type(await screen.findByLabelText(/approver name/i), "Kim");

  // Lee approved it from another console meanwhile.
  server.details[4] = detail({
    briefing_status: "approved",
    briefing: { ...BRIEFING, status: "approved", decided_by: "Lee", decided_at: "2030-01-01T00:01:00Z" },
  });
  await user.click(screen.getByRole("button", { name: "Approve" }));

  expect(await screen.findByText(/Approved by Lee/)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
});


test("one failed refresh doesn't stop polling while a report is processing", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const server: Server = {
    provider: "fake",
    reports: [summary({ status: "processing", verdict: null, brief_by_at: null, briefing_status: null })],
    details: {},
  };
  const fetchMock = serve(server);
  const base = fetchMock.getMockImplementation()!;
  let listCount = 0;
  fetchMock.mockImplementation((url: string, init?: RequestInit) => {
    if (url === "/api/reports" && !init?.method && ++listCount === 2) return Promise.reject(new TypeError("blip"));
    return base(url, init);
  });
  render(<App />);
  await waitFor(() => expect(listCalls(fetchMock)).toBe(1));

  await act(() => vi.advanceTimersByTimeAsync(2000)); // this refresh fails
  expect(listCalls(fetchMock)).toBe(2);

  await act(() => vi.advanceTimersByTimeAsync(2000)); // and polling carries on
  expect(listCalls(fetchMock)).toBe(3);
});
