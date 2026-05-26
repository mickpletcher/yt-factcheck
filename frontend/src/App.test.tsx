import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("disables fact check until a URL or upload is provided", () => {
    render(<App />);

    expect(screen.getByRole("button", { name: /run fact check/i })).toBeDisabled();
  });

  it("enables fact check when a YouTube URL is entered", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.type(
      screen.getByPlaceholderText("https://www.youtube.com/watch?v=..."),
      "https://www.youtube.com/watch?v=abc123"
    );

    expect(screen.getByRole("button", { name: /run fact check/i })).toBeEnabled();
  });
});
