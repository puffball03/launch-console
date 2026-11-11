import { render, screen } from "@testing-library/react";

import App from "../App";

test("renders the Mission Control console heading", () => {
  render(<App />);

  expect(
    screen.getByRole("heading", { name: /mission control/i }),
  ).toBeInTheDocument();
});

test("filing a report selects it in the console", async () => {
  const { default: userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 42, status: "processing" }), { status: 201 })),
  );
  render(<App />);

  await user.type(screen.getByLabelText(/name/i), "Ada");
  await user.selectOptions(screen.getByLabelText(/station/i), "WX");
  await user.type(screen.getByLabelText(/wind/i), "10");
  await user.type(screen.getByLabelText(/temp/i), "10");
  await user.type(screen.getByLabelText(/fuel/i), "99");
  await user.type(screen.getByLabelText(/note/i), "Gusts rising");
  await user.click(screen.getByRole("button", { name: /file report/i }));

  expect(await screen.findByText(/report #42 filed/i)).toBeInTheDocument();
  vi.unstubAllGlobals();
});
