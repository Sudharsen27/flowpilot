import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AiSettingsPage from "@/app/(app)/settings/ai/page";
import { isNavigationItemActive } from "@/lib/navigation";

describe("AI settings page", () => {
  it("renders the page sections and provider states", () => {
    render(<AiSettingsPage />);

    expect(screen.getByRole("heading", { name: "AI & Automation" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "AI Providers" })).toBeVisible();
    expect(screen.getByText("Groq")).toBeVisible();
    expect(screen.getByText("OpenRouter")).toBeVisible();
    expect(screen.getByText("Not configured")).toBeVisible();
    expect(screen.getAllByText("Coming soon").length).toBeGreaterThan(1);
  });

  it("renders every task configuration with disabled choices", () => {
    render(<AiSettingsPage />);

    for (const title of [
      "Agent Planning",
      "Lead Qualification",
      "Response Drafting",
      "CRM Analysis",
      "Document & Image Analysis",
    ]) {
      expect(screen.getByRole("heading", { name: title })).toBeVisible();
    }

    expect(screen.getAllByRole("combobox")).toHaveLength(10);
    expect(screen.getAllByRole("combobox").every((control) => control.hasAttribute("disabled"))).toBe(true);
    expect(screen.getByRole("combobox", { name: "Provider for Agent Planning" })).toBeDisabled();
  });

  it("uses labeled responsive regions for the page sections", () => {
    render(<AiSettingsPage />);

    expect(screen.getByRole("region", { name: "AI Providers" })).toHaveClass("grid");
    expect(screen.getByRole("region", { name: "AI Task Configuration" })).toHaveClass("grid");
    expect(screen.getByRole("region", { name: "Enterprise Controls" })).toHaveClass("grid");
  });

  it("shows truthful future states without fake usage numbers", () => {
    render(<AiSettingsPage />);

    expect(screen.getByRole("heading", { name: "AI Usage & Cost" })).toBeVisible();
    expect(screen.getAllByText("—")).toHaveLength(4);
    expect(screen.getByText("Usage tracking will become available with AI billing and model telemetry.")).toBeVisible();
    expect(screen.getAllByRole("textbox")).toHaveLength(5);
    expect(screen.getAllByRole("textbox").every((control) => control.hasAttribute("disabled"))).toBe(true);
  });

  it("keeps Settings active for the nested route", () => {
    expect(isNavigationItemActive("/settings/ai", "/settings")).toBe(true);
    expect(isNavigationItemActive("/settings/ai", "/analytics")).toBe(false);
  });
});