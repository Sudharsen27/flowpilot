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
  industry: { terms: [], weight: 50 },
  company_size: {
    minimum_employees: null,
    maximum_employees: null,
    weight: 50,
  },
  geography: { targets: [], weight: 50 },
  available_criteria: [
    "company",
    "enquiry",
    "industry",
    "company_size",
    "geography",
  ] as ("company" | "enquiry" | "industry" | "company_size" | "geography")[],
  unavailable_criteria: { buyer_role: "Buyer role is not available." },
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
        /Not configurable: Buyer role/,
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
        industry: { terms: [], weight: 50 },
        company_size: {
          minimum_employees: null,
          maximum_employees: null,
          weight: 50,
        },
        geography: { targets: [], weight: 50 },
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

    expect(screen.getByText(/Use up to 20 terms or locations/)).toBeVisible();
    expect(updateProfileMock).not.toHaveBeenCalled();
  });

  it("configures industry, employee bounds, and country-region targets", async () => {
    const user = userEvent.setup();
    updateProfileMock.mockResolvedValue({
      ...defaultProfile,
      industry: { terms: ["Software"], weight: 30 },
      company_size: {
        minimum_employees: 10,
        maximum_employees: 500,
        weight: 40,
      },
      geography: {
        targets: [{ country: "United States", region: "California" }],
        weight: 60,
      },
    });
    render(<IdealCustomerProfileSettings role="OWNER" />);

    await user.type(
      await screen.findByRole("textbox", { name: "Industry target terms" }),
      "Software",
    );
    await user.clear(screen.getByRole("spinbutton", { name: "Industry weight" }));
    await user.type(screen.getByRole("spinbutton", { name: "Industry weight" }), "30");
    await user.type(screen.getByLabelText("Minimum employees"), "10");
    await user.type(screen.getByLabelText("Maximum employees"), "500");
    await user.clear(screen.getByLabelText("Company-size weight"));
    await user.type(screen.getByLabelText("Company-size weight"), "40");
    await user.type(screen.getByLabelText("Country 1"), "United States");
    await user.type(screen.getByLabelText("Region 1"), "California");
    await user.clear(screen.getByLabelText("Geography weight"));
    await user.type(screen.getByLabelText("Geography weight"), "60");
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() =>
      expect(updateProfileMock).toHaveBeenCalledWith({
        company: { terms: [], weight: 50 },
        enquiry: { terms: [], weight: 50 },
        industry: { terms: ["Software"], weight: 30 },
        company_size: {
          minimum_employees: 10,
          maximum_employees: 500,
          weight: 40,
        },
        geography: {
          targets: [{ country: "United States", region: "California" }],
          weight: 60,
        },
      }),
    );
  });

  it("rejects a reversed employee range before submission", async () => {
    const user = userEvent.setup();
    render(<IdealCustomerProfileSettings role="OWNER" />);

    await user.type(await screen.findByLabelText("Minimum employees"), "500");
    await user.type(screen.getByLabelText("Maximum employees"), "10");
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    expect(
      screen.getByText(/valid inclusive employee bounds/),
    ).toBeVisible();
    expect(updateProfileMock).not.toHaveBeenCalled();
  });
});
