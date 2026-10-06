import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AiSettingsPage from "@/app/(app)/settings/ai/page";
import { ApiError } from "@/lib/api/client";
import { getRuntimeConfiguration } from "@/lib/api/runtime";
import { isNavigationItemActive } from "@/lib/navigation";
import type { RuntimeConfiguration } from "@/types/api";

vi.mock("@/lib/api/runtime", () => ({
  getRuntimeConfiguration: vi.fn(),
}));

const getRuntimeConfigurationMock = vi.mocked(getRuntimeConfiguration);

function configuration(
  overrides: Partial<RuntimeConfiguration> = {},
): RuntimeConfiguration {
  return {
    source: "environment",
    ai_provider: "groq",
    ai_provider_label: "Groq",
    ai_model: "openai/gpt-oss-20b",
    ai_status: "configured",
    human_decision_provider: "typesafe",
    human_decision_status: "not_configured",
    email_provider_label: "Resend",
    email_status: "configured",
    sender_address: "sales@example.com",
    sender_status: "configured",
    ...overrides,
  };
}

describe("AI settings page", () => {
  beforeEach(() => {
    getRuntimeConfigurationMock.mockReset();
  });

  it("shows a loading state before configuration arrives", () => {
    getRuntimeConfigurationMock.mockReturnValue(new Promise(() => undefined));
    render(<AiSettingsPage />);
    expect(screen.getByText("Loading AI configuration")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows configured runtime status without secrets or editable controls", async () => {
    getRuntimeConfigurationMock.mockResolvedValue(configuration());
    render(<AiSettingsPage />);
    expect(await screen.findByText("Groq")).toBeVisible();
    expect(screen.getByText("openai/gpt-oss-20b")).toBeVisible();
    expect(screen.getByText("AI configured")).toBeVisible();
    expect(screen.getByText("sales@example.com")).toBeVisible();
    expect(screen.getByText("Resend")).toBeVisible();
    expect(screen.getAllByText("Not configured").length).toBeGreaterThan(0);
    expect(screen.getByText(/not edited for each organization/)).toBeVisible();
    expect(screen.queryByText("sk-test-secret")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("shows not configured when providers have no credentials", async () => {
    getRuntimeConfigurationMock.mockResolvedValue(
      configuration({
        ai_provider: "openai",
        ai_provider_label: "OpenAI",
        ai_model: "gpt-4o-mini",
        ai_status: "not_configured",
        email_status: "not_configured",
        sender_address: null,
        sender_status: "not_configured",
      }),
    );
    render(<AiSettingsPage />);
    expect(await screen.findByText("OpenAI")).toBeVisible();
    expect(screen.getByText("gpt-4o-mini")).toBeVisible();
    expect(screen.getAllByText("Not configured").length).toBeGreaterThan(1);
    expect(screen.queryByText("AI configured")).not.toBeInTheDocument();
  });

  it("shows an unavailable error and retries", async () => {
    const user = userEvent.setup();
    getRuntimeConfigurationMock
      .mockRejectedValueOnce(new ApiError("offline", 503))
      .mockResolvedValueOnce(configuration());
    render(<AiSettingsPage />);
    expect(await screen.findByRole("heading", { name: "AI unavailable" })).toBeVisible();
    expect(screen.getByText(/could not be reached/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("AI configured")).toBeVisible();
    expect(getRuntimeConfigurationMock).toHaveBeenCalledTimes(2);
  });

  it("uses a compact responsive configuration region", async () => {
    getRuntimeConfigurationMock.mockResolvedValue(configuration());
    render(<AiSettingsPage />);
    const region = await screen.findByRole("region", { name: "Runtime configuration" });
    expect(region).toHaveClass("max-w-3xl", "grid");
  });

  it("keeps Settings active for the nested route", () => {
    expect(isNavigationItemActive("/settings/ai", "/settings")).toBe(true);
    expect(isNavigationItemActive("/settings/ai", "/analytics")).toBe(false);
  });
});
