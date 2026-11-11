import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ReportForm from "../components/ReportForm";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function respondWith(status: number, body: unknown) {
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

async function fillValidReport(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/name/i), "Ada Ruiz");
  await user.selectOptions(screen.getByLabelText(/station/i), "PROP");
  await user.type(screen.getByLabelText(/wind/i), "12.5");
  await user.type(screen.getByLabelText(/temp/i), "-3");
  await user.type(screen.getByLabelText(/fuel/i), "99.1");
  await user.type(screen.getByLabelText(/note/i), "LOX valve slow to close.");
}

test("sends all six fields to the API, readings as numbers", async () => {
  const user = userEvent.setup();
  respondWith(201, { id: 7, status: "processing" });
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, init] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/reports");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body)).toEqual({
    engineer_name: "Ada Ruiz",
    station: "PROP",
    wind_knots: 12.5,
    temp_c: -3,
    fuel_pct: 99.1,
    note: "LOX valve slow to close.",
  });
});

test("an empty form shows a message for every field and sends nothing", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/name/i)).toHaveAccessibleDescription("Name is required.");
  expect(screen.getByLabelText(/station/i)).toHaveAccessibleDescription("Station is required.");
  expect(screen.getByLabelText(/wind/i)).toHaveAccessibleDescription("Wind is required.");
  expect(screen.getByLabelText(/temp/i)).toHaveAccessibleDescription("Temperature is required.");
  expect(screen.getByLabelText(/fuel/i)).toHaveAccessibleDescription("Fuel is required.");
  expect(screen.getByLabelText(/note/i)).toHaveAccessibleDescription("Note is required.");
  expect(screen.getByLabelText(/name/i)).toHaveAttribute("aria-invalid", "true");
});

test("a whitespace-only name counts as blank", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.clear(screen.getByLabelText(/name/i));
  await user.type(screen.getByLabelText(/name/i), "   ");
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/name/i)).toHaveAccessibleDescription("Name is required.");
});

test("negative wind or fuel is caught before sending; negative temperature is fine", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.clear(screen.getByLabelText(/wind/i));
  await user.type(screen.getByLabelText(/wind/i), "-1");
  await user.clear(screen.getByLabelText(/fuel/i));
  await user.type(screen.getByLabelText(/fuel/i), "-2");
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/wind/i)).toHaveAccessibleDescription("Wind cannot be negative.");
  expect(screen.getByLabelText(/fuel/i)).toHaveAccessibleDescription("Fuel cannot be negative.");
  expect(screen.getByLabelText(/temp/i)).not.toHaveAttribute("aria-invalid", "true");
});

test("a note over 2000 characters is caught before sending", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.clear(screen.getByLabelText(/note/i));
  await user.click(screen.getByLabelText(/note/i));
  await user.paste("x".repeat(2001));
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/note/i)).toHaveAccessibleDescription(
    "Note must be 2000 characters or fewer.",
  );
});

test("fixing a field clears its message", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await user.click(screen.getByRole("button", { name: /file report/i }));
  await user.type(screen.getByLabelText(/name/i), "Ada");

  expect(screen.getByLabelText(/name/i)).not.toHaveAccessibleDescription("Name is required.");
});

test("server 422 messages appear next to their fields", async () => {
  const user = userEvent.setup();
  const onFiled = vi.fn();
  respondWith(422, {
    detail: "Invalid report",
    errors: { station: "Station must be one of PROP, GNC, TELEM, RANGE, WX.", note: "Note is required." },
  });
  render(<ReportForm onFiled={onFiled} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByText("Note is required.")).toBeInTheDocument();
  expect(screen.getByLabelText(/station/i)).toHaveAccessibleDescription(
    "Station must be one of PROP, GNC, TELEM, RANGE, WX.",
  );
  expect(screen.getByLabelText(/note/i)).toHaveAccessibleDescription("Note is required.");
  expect(onFiled).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/name/i)).toHaveValue("Ada Ruiz");
});

test("a server error that isn't about one field is shown above the button", async () => {
  const user = userEvent.setup();
  respondWith(422, { detail: "Invalid report", errors: { _body: "Request body must be a JSON object." } });
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Request body must be a JSON object.");
});

test("a network failure is reported and the form keeps its values", async () => {
  const user = userEvent.setup();
  fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent(/could not reach the server/i);
  expect(screen.getByLabelText(/note/i)).toHaveValue("LOX valve slow to close.");
});

test("on success the form clears and the new report is selected", async () => {
  const user = userEvent.setup();
  const onFiled = vi.fn();
  respondWith(201, { id: 42, status: "processing" });
  render(<ReportForm onFiled={onFiled} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(onFiled).toHaveBeenCalledWith(42);
  expect(screen.getByLabelText(/name/i)).toHaveValue("");
  expect(screen.getByLabelText(/station/i)).toHaveValue("");
  expect(screen.getByLabelText(/wind/i)).toHaveValue(null);
  expect(screen.getByLabelText(/note/i)).toHaveValue("");
});

test("the button is disabled while sending, so a report can't be filed twice", async () => {
  const user = userEvent.setup();
  let finish: (r: Response) => void = () => {};
  fetchMock.mockReturnValueOnce(new Promise<Response>((resolve) => (finish = resolve)));
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  const button = screen.getByRole("button", { name: /file report/i });
  await user.click(button);

  expect(button).toBeDisabled();
  await user.click(button);
  expect(fetchMock).toHaveBeenCalledTimes(1);

  finish(new Response(JSON.stringify({ id: 1, status: "processing" }), { status: 201 }));
  await vi.waitFor(() => expect(button).toBeEnabled());
});

test("a server error with a plain-text body is shown as a server error, not a network failure", async () => {
  const user = userEvent.setup();
  fetchMock.mockResolvedValueOnce(
    new Response("Internal Server Error", { status: 500, headers: { "content-type": "text/plain" } }),
  );
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Server error (500).");
  expect(alert).not.toHaveTextContent(/could not reach/i);
  expect(screen.getByLabelText(/note/i)).toHaveValue("LOX valve slow to close.");
});

test("a JSON error with only a detail message shows that message", async () => {
  const user = userEvent.setup();
  respondWith(404, { detail: "Not Found" });
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Not Found");
});

test("a name over 100 characters is caught before sending", async () => {
  const user = userEvent.setup();
  render(<ReportForm onFiled={() => {}} />);

  await fillValidReport(user);
  await user.clear(screen.getByLabelText(/name/i));
  await user.click(screen.getByLabelText(/name/i));
  await user.paste("A".repeat(101));
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(fetchMock).not.toHaveBeenCalled();
  expect(screen.getByLabelText(/name/i)).toHaveAccessibleDescription(
    "Name must be 100 characters or fewer.",
  );
});
