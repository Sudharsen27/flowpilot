import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WebsiteEnquirySettings } from "@/components/settings/website-enquiry-settings";
import { getAgents } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import {
  getWebsiteCaptureSettings,
  submitPublicEnquiry,
  updateWebsiteCaptureSettings,
} from "@/lib/api/website-capture";
import type { Agent, WebsiteCaptureSettings } from "@/types/api";

vi.mock("@/lib/api/website-capture", () => ({
  getWebsiteCaptureSettings: vi.fn(),
  updateWebsiteCaptureSettings: vi.fn(),
  submitPublicEnquiry: vi.fn(),
}));

vi.mock("@/lib/api/agents", () => ({
  getAgents: vi.fn(),
}));

const getSettingsMock = vi.mocked(getWebsiteCaptureSettings);
const updateSettingsMock = vi.mocked(updateWebsiteCaptureSettings);
const getAgentsMock = vi.mocked(getAgents);
const submitPublicEnquiryMock = vi.mocked(submitPublicEnquiry);

function captureSettings(
  overrides: Partial<WebsiteCaptureSettings> = {},
): WebsiteCaptureSettings {
  return {
    website_capture_enabled: false,
    sales_agent_auto_start_enabled: false,
    default_sales_agent_id: null,
    ...overrides,
  };
}

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "agent-sales-1",
    name: "Inbound qualifier",
    description: "Qualifies new inbound leads.",
    agent_type: "SALES",
    system_instructions: "Ask concise qualification questions.",
    status: "ACTIVE",
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-09T10:00:00Z",
    ...overrides,
  };
}

const eligibleAgents: Agent[] = [
  agent(),
  agent({
    id: "agent-sales-2",
    name: "Outbound closer",
    status: "READY",
  }),
];

async function findAutoStartSwitch() {
  const toggle = await screen.findByRole("switch", {
    name: "Start Sales Agent automatically",
  });
  await waitFor(() => expect(toggle).toBeEnabled());
  return toggle;
}

describe("Website enquiry settings", () => {
  beforeEach(() => {
    getSettingsMock.mockReset();
    updateSettingsMock.mockReset();
    getAgentsMock.mockReset();
    submitPublicEnquiryMock.mockReset();
    getAgentsMock.mockResolvedValue(eligibleAgents);
  });

  it("shows the disabled state for owners", async () => {
    getSettingsMock.mockResolvedValue(captureSettings());
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    expect(
      await screen.findByText("Website capture is off. Enquiries cannot be submitted."),
    ).toBeVisible();
    expect(screen.getByText("Website Capture Enabled")).toBeVisible();
    expect(screen.getByText("Off")).toBeVisible();
    expect(screen.getByRole("button", { name: "Enable website enquiries" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Copy URL" })).not.toBeInTheDocument();
    expect(
      screen.getByRole("switch", { name: "Start Sales Agent automatically" }),
    ).toBeDisabled();
    expect(screen.queryByLabelText("Default Sales Agent")).not.toBeInTheDocument();
  });

  it("shows the enabled URL and copies it", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="ADMIN" />);
    expect(await screen.findByText(/Enquiry form URL/)).toBeVisible();
    expect(screen.getByText("On")).toBeVisible();
    expect(screen.getByText(/\/capture\/acme/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Copy URL" }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeVisible();
  });

  it("lets owners enable capture without auto-start", async () => {
    const user = userEvent.setup();
    getSettingsMock.mockResolvedValue(captureSettings());
    updateSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(
      await screen.findByRole("button", { name: "Enable website enquiries" }),
    );
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({
        website_capture_enabled: true,
        sales_agent_auto_start_enabled: false,
        default_sales_agent_id: null,
      }),
    );
    expect(screen.getByText("On")).toBeVisible();
    expect(submitPublicEnquiryMock).not.toHaveBeenCalled();
  });

  it("hides the Sales Agent selector while auto-start is off", async () => {
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    expect(
      await screen.findByRole("switch", { name: "Start Sales Agent automatically" }),
    ).not.toBeChecked();
    expect(screen.queryByLabelText("Default Sales Agent")).not.toBeInTheDocument();
  });

  it("requires an eligible Sales Agent before saving auto-start", async () => {
    const user = userEvent.setup();
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    updateSettingsMock.mockResolvedValue(
      captureSettings({
        website_capture_enabled: true,
        sales_agent_auto_start_enabled: true,
        default_sales_agent_id: "agent-sales-1",
      }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    expect(await screen.findByLabelText(/Default Sales Agent/)).toBeVisible();
    expect(screen.getByRole("option", { name: "Inbound qualifier" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Outbound closer" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save Sales Agent settings" }),
    ).toBeDisabled();
    expect(updateSettingsMock).not.toHaveBeenCalled();
    await user.selectOptions(screen.getByLabelText(/Default Sales Agent/), "agent-sales-1");
    await user.click(screen.getByRole("button", { name: "Save Sales Agent settings" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({
        website_capture_enabled: true,
        sales_agent_auto_start_enabled: true,
        default_sales_agent_id: "agent-sales-1",
      }),
    );
    expect(submitPublicEnquiryMock).not.toHaveBeenCalled();
  });

  it("does not silently select a Sales Agent", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([agent()]);
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    expect(await screen.findByLabelText(/Default Sales Agent/)).toHaveValue("");
  });

  it("excludes ineligible agents from the selector", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([
      agent(),
      agent({
        id: "agent-support-1",
        name: "Support bot",
        agent_type: "SUPPORT",
        status: "ACTIVE",
      }),
      agent({
        id: "agent-draft-1",
        name: "Draft qualifier",
        status: "DRAFT",
      }),
      agent({
        id: "agent-paused-1",
        name: "Paused qualifier",
        status: "PAUSED",
      }),
    ]);
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    expect(await screen.findByRole("option", { name: "Inbound qualifier" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Support bot" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Draft qualifier" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Paused qualifier" })).not.toBeInTheDocument();
  });

  it("does not enable auto-start when no eligible Sales Agent exists", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockResolvedValue([
      agent({
        id: "agent-draft-1",
        name: "Draft qualifier",
        status: "DRAFT",
      }),
    ]);
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    expect(
      await screen.findByText(
        "Create a READY or ACTIVE Sales Agent before enabling automatic start.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("switch", { name: "Start Sales Agent automatically" }),
    ).not.toBeChecked();
    expect(screen.queryByLabelText("Default Sales Agent")).not.toBeInTheDocument();
    expect(updateSettingsMock).not.toHaveBeenCalled();
  });

  it("shows an error when Sales Agents fail to load", async () => {
    const user = userEvent.setup();
    getAgentsMock.mockRejectedValue(new Error("agents failed"));
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    expect(await screen.findByText("Sales Agents could not be loaded. Try again.")).toBeVisible();
    expect(updateSettingsMock).not.toHaveBeenCalled();
  });

  it("displays existing error UI when save fails", async () => {
    const user = userEvent.setup();
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    updateSettingsMock.mockRejectedValue(new ApiError("Request failed: 500", 500));
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(await findAutoStartSwitch());
    await user.selectOptions(
      await screen.findByLabelText(/Default Sales Agent/),
      "agent-sales-1",
    );
    await user.click(screen.getByRole("button", { name: "Save Sales Agent settings" }));
    expect(
      await screen.findByText("Website capture could not be updated. Please try again."),
    ).toBeVisible();
    expect(submitPublicEnquiryMock).not.toHaveBeenCalled();
  });

  it("confirms before disabling capture and clears auto-start", async () => {
    const user = userEvent.setup();
    getSettingsMock.mockResolvedValue(
      captureSettings({
        website_capture_enabled: true,
        sales_agent_auto_start_enabled: true,
        default_sales_agent_id: "agent-sales-1",
      }),
    );
    updateSettingsMock.mockResolvedValue(captureSettings());
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(
      await screen.findByRole("button", { name: "Disable website enquiries" }),
    );
    expect(screen.getByRole("heading", { name: "Disable website enquiries?" })).toBeVisible();
    expect(
      screen.getByText(/Automatic Sales Agent start will also stop/),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Disable" }));
    await waitFor(() =>
      expect(updateSettingsMock).toHaveBeenCalledWith({
        website_capture_enabled: false,
        sales_agent_auto_start_enabled: false,
        default_sales_agent_id: null,
      }),
    );
    expect(submitPublicEnquiryMock).not.toHaveBeenCalled();
  });

  it("keeps members read-only", async () => {
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="MEMBER" />);
    expect(await screen.findByText("Only owners and admins can change this.")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Enable website enquiries" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disable website enquiries" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy URL" })).toBeVisible();
    expect(
      screen.getByRole("switch", { name: "Start Sales Agent automatically" }),
    ).toBeDisabled();
  });

  it("does not claim Inbox, Activity, or automatic email", async () => {
    getSettingsMock.mockResolvedValue(captureSettings());
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await screen.findByText("Off");
    expect(screen.queryByText(/inbox/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/activity feed/i)).not.toBeInTheDocument();
    expect(
      screen.getByText(/email is not sent until a person approves a response/i),
    ).toBeVisible();
  });

  it("loads Sales Agents from the authenticated organization list", async () => {
    getSettingsMock.mockResolvedValue(
      captureSettings({ website_capture_enabled: true }),
    );
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await screen.findByText("On");
    await waitFor(() =>
      expect(getAgentsMock).toHaveBeenCalledWith({ agentType: "SALES" }),
    );
    expect(getAgentsMock.mock.calls[0]?.[0]).not.toHaveProperty("organization_id");
  });
});
