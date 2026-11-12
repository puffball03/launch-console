import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { TraceStep } from "../api";
import TracePanel from "../components/TracePanel";

function step(over: Partial<TraceStep>): TraceStep {
  return {
    seq: 1, step: "sort", kind: "model", model: "mc-fast", status: "ok", input_tokens: 108,
    output_tokens: 11, cost_usd: "0.0000163", duration_ms: 412, input_preview: "<note>\nValve fine.\n</note>",
    output_preview: '{"subsystem": "propulsion", "severity": "low"}', error: null, ...over,
  };
}

const TRACE: TraceStep[] = [
  step({ seq: 1, step: "limits", kind: "code", model: null, input_tokens: 0, output_tokens: 0, cost_usd: "0", duration_ms: 0 }),
  step({ seq: 2, step: "sort" }),
  step({ seq: 3, step: "check_injection", status: "fallback", error: "Invalid check reply: not JSON" }),
  step({ seq: 4, step: "draft_1", model: "mc-smart", status: "error", input_tokens: 0, output_tokens: 0, cost_usd: "0", error: "TimeoutError: slow" }),
];

test("one card per step, in pipeline order", () => {
  render(<TracePanel trace={TRACE} totalCostUsd="0.0000163" />);

  const cards = screen.getAllByRole("listitem");
  expect(cards).toHaveLength(4);
  expect(cards.map((c) => within(c).getByRole("heading").textContent)).toEqual([
    "limits", "sort", "check_injection", "draft_1",
  ]);
});

test("a model card shows its model, status, tokens, cost and duration", () => {
  render(<TracePanel trace={TRACE} totalCostUsd="0.0000163" />);

  const sort = screen.getAllByRole("listitem")[1];
  expect(within(sort).getByText("mc-fast")).toBeInTheDocument();
  expect(within(sort).getByText("ok")).toBeInTheDocument();
  expect(within(sort).getByText("108 in / 11 out")).toBeInTheDocument();
  expect(within(sort).getByText("$0.0000163")).toBeInTheDocument();
  expect(within(sort).getByText("412 ms")).toBeInTheDocument();
});

test("a code step says code and costs nothing", () => {
  render(<TracePanel trace={TRACE} totalCostUsd="0" />);

  const limits = screen.getAllByRole("listitem")[0];
  expect(within(limits).getByText("code")).toBeInTheDocument();
  expect(within(limits).getByText("0 in / 0 out")).toBeInTheDocument();
  expect(within(limits).getByText("$0")).toBeInTheDocument();
});

test("fallback and error steps are styled apart and show their error", () => {
  render(<TracePanel trace={TRACE} totalCostUsd="0" />);

  const [, ok, fallback, error] = screen.getAllByRole("listitem");
  expect(ok).toHaveClass("trace-ok");
  expect(fallback).toHaveClass("trace-fallback");
  expect(error).toHaveClass("trace-error");
  expect(within(fallback).getByText("Invalid check reply: not JSON")).toBeInTheDocument();
  expect(within(error).getByText("TimeoutError: slow")).toBeInTheDocument();
});


test("the header shows the report's total cost exactly as the API sent it", () => {
  render(<TracePanel trace={TRACE} totalCostUsd="0.0070973" />);

  expect(screen.getByRole("heading", { name: /trace/i })).toHaveTextContent("Total cost $0.0070973");
});

test("previews are collapsed until opened", async () => {
  const user = userEvent.setup();
  render(<TracePanel trace={TRACE} totalCostUsd="0" />);

  const sort = screen.getAllByRole("listitem")[1];
  const details = within(sort).getByText("Input and output").closest("details")!;
  expect(details).not.toHaveAttribute("open");

  await user.click(within(sort).getByText("Input and output"));

  expect(details).toHaveAttribute("open");
  expect(within(sort).getByText(/Valve fine\./)).toBeInTheDocument();
  expect(within(sort).getByText(/"subsystem": "propulsion"/)).toBeInTheDocument();
});

test("a step without previews has nothing to open", () => {
  render(<TracePanel trace={[step({ input_preview: null, output_preview: null })]} totalCostUsd="0" />);

  expect(screen.queryByText("Input and output")).not.toBeInTheDocument();
});

test("an empty trace says no steps have run yet", () => {
  render(<TracePanel trace={[]} totalCostUsd="0" />);

  expect(screen.getByText(/no steps have run yet/i)).toBeInTheDocument();
});
