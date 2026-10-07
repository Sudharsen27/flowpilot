import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/(auth)/login/page";
import RegisterPage from "@/app/(auth)/register/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    signIn: vi.fn(),
    signUp: vi.fn(),
  }),
}));

describe("auth pages", () => {
  it("frames sign-in as an approval workspace", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
    expect(
      screen.getByRole("heading", {
        name: "New enquiries become replies your team can send.",
      }),
    ).toBeVisible();
    expect(screen.getByText("Approve")).toBeVisible();
    expect(screen.getByText("Example. A person approves the send.")).toBeVisible();
    expect(screen.getByText("Example")).toBeVisible();
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute(
      "href",
      "/register",
    );
    expect(screen.getByRole("button", { name: "Sign in" })).toBeVisible();
  });

  it("creates an organization without calling the form a development stub", () => {
    render(<RegisterPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Create account" })).toBeVisible();
    expect(screen.getByText(/owner membership/)).toBeVisible();
    expect(screen.queryByText(/development sign-up/i)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("button", { name: "Create account" })).toBeVisible();
  });
});
