import { render, screen } from "@testing-library/react";

import App from "../App";

test("renders the Mission Control console heading", () => {
  render(<App />);

  expect(
    screen.getByRole("heading", { name: /mission control/i }),
  ).toBeInTheDocument();
});
