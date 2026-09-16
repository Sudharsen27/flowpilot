import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { WebsiteEnquirySettings } from "@/components/settings/website-enquiry-settings";
import {
  getWebsiteCaptureSettings,
  updateWebsiteCaptureSettings,
} from "@/lib/api/website-capture";

vi.mock("@/lib/api/website-capture", () => ({
  getWebsiteCaptureSettings: vi.fn(),
  updateWebsiteCaptureSettings: vi.fn(),
}));

const getSettingsMock = vi.mocked(getWebsiteCaptureSettings);
const updateSettingsMock = vi.mocked(updateWebsiteCaptureSettings);

describe("Website enquiry settings", () => {
  beforeEach(() => {
    getSettingsMock.mockReset();
    updateSettingsMock.mockReset();
  });

  it("shows the disabled state for owners", async () => {
    getSettingsMock.mockResolvedValue({ website_capture_enabled: false });
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    expect(
      await screen.findByText("Website capture is off. Enquiries cannot be submitted."),
    ).toBeVisible();
    expect(screen.getByText("Off")).toBeVisible();
    expect(screen.getByRole("button", { name: "Enable website enquiries" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Copy URL" })).not.toBeInTheDocument();
  });

  it("shows the enabled URL and copies it", async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    getSettingsMock.mockResolvedValue({ website_capture_enabled: true });
    render(<WebsiteEnquirySettings slug="acme" role="ADMIN" />);
    expect(await screen.findByText(/Enquiry form URL/)).toBeVisible();
    expect(screen.getByText("On")).toBeVisible();
    expect(screen.getByText(/\/capture\/acme/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Copy URL" }));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeVisible();
  });

  it("lets owners enable capture", async () => {
    const user = userEvent.setup();
    getSettingsMock.mockResolvedValue({ website_capture_enabled: false });
    updateSettingsMock.mockResolvedValue({ website_capture_enabled: true });
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await user.click(
      await screen.findByRole("button", { name: "Enable website enquiries" }),
    );
    await waitFor(() => expect(updateSettingsMock).toHaveBeenCalledWith(true));
    expect(screen.getByText("On")).toBeVisible();
  });

  it("keeps members read-only", async () => {
    getSettingsMock.mockResolvedValue({ website_capture_enabled: true });
    render(<WebsiteEnquirySettings slug="acme" role="MEMBER" />);
    expect(await screen.findByText("Only owners and admins can change this.")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Enable website enquiries" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Disable website enquiries" }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy URL" })).toBeVisible();
  });

  it("does not claim Inbox or Activity", async () => {
    getSettingsMock.mockResolvedValue({ website_capture_enabled: false });
    render(<WebsiteEnquirySettings slug="acme" role="OWNER" />);
    await screen.findByText("Off");
    expect(screen.queryByText(/inbox/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/activity feed/i)).not.toBeInTheDocument();
    expect(
      screen.getByText(/will not start the Sales Agent or send email automatically/),
    ).toBeVisible();
  });
});
