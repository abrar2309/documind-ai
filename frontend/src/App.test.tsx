import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";

describe("DocuMind application", () => {
  it("renders the sign-in interface", () => {
    localStorage.clear();
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Welcome back" })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: "Sign in" })
    ).toBeInTheDocument();

    expect(
      screen.getByPlaceholderText("you@example.com")
    ).toBeInTheDocument();
  });

  it("allows switching to account registration", async () => {
    localStorage.clear();
    render(<App />);

    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();

    await user.click(
      screen.getByRole("button", { name: /create account/i })
    );

    expect(
      screen.getByRole("heading", { name: "Create your account" })
    ).toBeInTheDocument();

    expect(
      screen.getByPlaceholderText("Your name")
    ).toBeInTheDocument();
  });
});
