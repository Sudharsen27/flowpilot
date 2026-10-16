import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IdealCustomerProfileSettings } from "@/components/settings/ideal-customer-profile-settings";
import {
  getIdealCustomerProfile,
  updateIdealCustomerProfile,
} from "@/lib/api/ideal-customer-profile";

vi.mock("@/lib/api/ideal-customer-profile", () => ({
  getIdealCustomerProfile: vi.fn(),
  updateIdealCustomerProfile: vi.fn(),
}));

const defaultProfile = {
  company: { terms: [], weight: 50 },
  enquiry: { terms: [], weight: 50 },
  available_criteria: ["company", "enquiry"] as ("company" | "enquiry")[],
  unavailable_criteria: {
    industry: "Industry is not stored.",
    employee_range: "Company size is not stored.",
    geographic_region: "Region is not stored.",
    buyer_role: "Buyer role is not stored.",
  },
  configuration_valid: true,
};

const getProfileMock = vi.mocked(getIdealCustomerProfile);
const updateProfileMock = vi.mocked(updateIdealCustomerProfile);

describe("IdealCustomerProfileSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getProfileMock.mockResolvedValue(defaultProfile);
  });

  it("loads defaults, identifies unavailable criteria, and saves normalized input", async () => {
    const user = userEvent.setup();
    updateProfileMock.mockResolvedValue({
      ...defaultProfile,
      company: { terms: ["Acme"], weight: 70 },
    });
    render(<IdealCustomerProfileSettings role="OWNER" />);

    const companyTerms = await screen.findByRole("textbox", {
      name: "Company match terms",
    });
    expect(
      screen.getByText(
        /Not configurable: Industry, Company size, Region, Buyer role/,
      ),
    ).toBeVisible();
    await user.type(companyTerms, "Acme");
    const weight = screen.getAllByRole("spinbutton")[0];
    await user.clear(weight);
    await user.type(weight, "70");
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(updateProfileMock).toHaveBeenCalledWith({
        company: { terms: ["Acme"], weight: 70 },
        enquiry: { terms: [], weight: 50 },
      }),
    );
    expect(screen.getByText("Profile saved.")).toBeVisible();
  });

  it("keeps member configuration read-only", async () => {
    render(<IdealCustomerProfileSettings role="MEMBER" />);

    expect(
      await screen.findByRole("textbox", { name: "Company match terms" }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: "Save profile" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Only owners and admins can change this profile."),
    ).toBeVisible();
    expect(updateProfileMock).not.toHaveBeenCalled();
  });

  it("warns about invalid stored configuration and can save a repair", async () => {
    const user = userEvent.setup();
    getProfileMock.mockResolvedValue({
      ...defaultProfile,
      configuration_valid: false,
    });
    updateProfileMock.mockResolvedValue(defaultProfile);
    render(<IdealCustomerProfileSettings role="ADMIN" />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The saved profile is invalid. Save a corrected profile to restore prospect scoring.",
    );
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(updateProfileMock).toHaveBeenCalledOnce());
    expect(screen.getByText("Profile saved.")).toBeVisible();
  });

  it("shows a loading state while the profile request is pending", () => {
    getProfileMock.mockReturnValue(new Promise(() => undefined));
    render(<IdealCustomerProfileSettings role="ADMIN" />);

    expect(
      screen.getByText("Loading prospect fit settings"),
    ).toBeInTheDocument();
  });

  it("retries load errors and validates term limits before saving", async () => {
    const user = userEvent.setup();
    getProfileMock
      .mockRejectedValueOnce(new Error("unavailable"))
      .mockResolvedValueOnce(defaultProfile);
    render(<IdealCustomerProfileSettings role="ADMIN" />);
    expect(
      await screen.findByRole("heading", {
        name: "Prospect fit settings could not be loaded",
      }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    const companyTerms = await screen.findByRole("textbox", {
      name: "Company match terms",
    });
    await user.type(
      companyTerms,
      Array.from({ length: 21 }, (_, index) => `term${index}`).join("\n"),
    );
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    expect(screen.getByText(/Use up to 20 terms per field/)).toBeVisible();
    expect(updateProfileMock).not.toHaveBeenCalled();
  });
});
