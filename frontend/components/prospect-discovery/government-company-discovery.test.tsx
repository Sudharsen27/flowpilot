import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GovernmentCompanyDiscovery } from "@/components/prospect-discovery/government-company-discovery";
import { ApiError } from "@/lib/api/client";
import { searchGovernmentCompanies } from "@/lib/api/prospect-discovery";
import { getRuntimeConfiguration } from "@/lib/api/runtime";
import type {
  GovernmentCompanyDiscoveryResponse,
  RuntimeConfiguration,
} from "@/types/api";

vi.mock("@/lib/api/prospect-discovery", () => ({
  searchGovernmentCompanies: vi.fn(),
}));

vi.mock("@/lib/api/runtime", () => ({
  getRuntimeConfiguration: vi.fn(),
}));

const searchMock = vi.mocked(searchGovernmentCompanies);
const runtimeMock = vi.mocked(getRuntimeConfiguration);

function configuration(
  overrides: Partial<RuntimeConfiguration> = {},
): RuntimeConfiguration {
  return {
    source: "environment",
    ai_provider: "openai",
    ai_provider_label: "OpenAI",
    ai_model: "gpt-4o-mini",
    ai_status: "not_configured",
    human_decision_provider: "typesafe",
    human_decision_status: "not_configured",
    email_provider_label: "Resend",
    email_status: "not_configured",
    sender_address: null,
    sender_status: "not_configured",
    government_company_discovery_available: false,
    government_company_discovery_max_page_size: 100,
    government_company_discovery_max_offset: 100_000,
    ...overrides,
  };
}

function governmentResponse(
  overrides: Partial<GovernmentCompanyDiscoveryResponse> = {},
): GovernmentCompanyDiscoveryResponse {
  return {
    source: "GOVERNMENT",
    items: [
      {
        CIN: "U12345DL2001PLC123456",
        CompanyName: "Example Registry Company",
        CompanyStateCode: "DL",
        OptionalSourceField: null,
      },
    ],
    normalized_items: [
      {
        cin: "U12345DL2001PLC123456",
        company_name: "Example Registry Company",
        company_status: null,
        company_class: null,
        company_category: null,
        company_sub_category: null,
        authorized_capital: null,
        paid_up_capital: null,
        number_of_members: null,
        date_of_incorporation: "2001-01-01",
        registered_address: null,
        company_state_code: "DL",
        registrar_of_companies: null,
        principal_business_activity: null,
        industrial_classification_code: null,
        attribution: {
          provider: "data.gov.in",
          dataset: "Registrars of Companies (RoC)-wise Company Master Data",
          resource_uuid: "4dbe5667-7b6b-41d7-82af-211562424d9a",
          endpoint:
            "https://api.data.gov.in/resource/4dbe5667-7b6b-41d7-82af-211562424d9a",
          attribution:
            "Government of India, Ministry of Corporate Affairs, via data.gov.in.",
          licensing_status: "PENDING_WRITTEN_CLARIFICATION",
        },
        retrieved_at: "2026-10-22T07:52:45Z",
      },
    ],
    total: 3,
    offset: 0,
    page_size: 1,
    has_more: true,
    next_offset: 1,
    attribution: {
      provider: "data.gov.in",
      dataset: "Registrars of Companies (RoC)-wise Company Master Data",
      resource_uuid: "4dbe5667-7b6b-41d7-82af-211562424d9a",
      endpoint:
        "https://api.data.gov.in/resource/4dbe5667-7b6b-41d7-82af-211562424d9a",
      attribution:
        "Government of India, Ministry of Corporate Affairs, via data.gov.in.",
      licensing_status: "PENDING_WRITTEN_CLARIFICATION",
    },
    ...overrides,
  };
}

describe("Government Company Discovery", () => {
  beforeEach(() => {
    searchMock.mockReset();
    runtimeMock.mockReset();
  });

  it("keeps search unavailable when backend says provider disabled", async () => {
    runtimeMock.mockResolvedValue(configuration());
    render(<GovernmentCompanyDiscovery />);

    expect(
      await screen.findByText(/provider is disabled or not configured/i),
    ).toBeVisible();
    expect(screen.getByLabelText("CompanyStateCode")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Search government records" }),
    ).toBeDisabled();
    expect(searchMock).not.toHaveBeenCalled();
  });

  it("fails closed when backend availability cannot be confirmed", async () => {
    runtimeMock.mockRejectedValue(new Error("runtime unavailable"));
    render(<GovernmentCompanyDiscovery />);

    expect(
      await screen.findByText(/Availability could not be confirmed/i),
    ).toBeVisible();
    expect(screen.getByLabelText("CompanyStateCode")).toBeDisabled();
    expect(searchMock).not.toHaveBeenCalled();
  });

  it("fails closed when the runtime response omits the page-size limit", async () => {
    runtimeMock.mockResolvedValue(
      configuration({
        government_company_discovery_available: true,
        government_company_discovery_max_page_size:
          undefined as unknown as number,
      }),
    );
    render(<GovernmentCompanyDiscovery />);

    expect(
      await screen.findByText(/server returned invalid discovery limits/i),
    ).toBeVisible();
    expect(screen.getByLabelText("CompanyStateCode")).toBeDisabled();
    const pageSizeSelect = screen.getByLabelText("Records per page");
    expect(pageSizeSelect).toBeDisabled();
    expect(pageSizeSelect.getAttribute("value")).not.toBe("NaN");
    expect(
      screen.getByRole("button", { name: "Search government records" }),
    ).toBeDisabled();
    expect(searchMock).not.toHaveBeenCalled();
  });

  it("submits only supported filters and displays source-provided fields and attribution", async () => {
    const user = userEvent.setup();
    runtimeMock.mockResolvedValue(
      configuration({
        government_company_discovery_available: true,
        government_company_discovery_max_page_size: 1,
      }),
    );
    searchMock.mockResolvedValue(governmentResponse());
    render(<GovernmentCompanyDiscovery />);

    await screen.findByRole("button", { name: "Search government records" });
    await user.type(screen.getByLabelText("CompanyStateCode"), "DL");
    expect(screen.getByLabelText("Records per page")).toHaveValue("1");
    await user.click(
      screen.getByRole("button", { name: "Search government records" }),
    );

    expect(searchMock).toHaveBeenCalledWith({
      state_code: "DL",
      offset: 0,
      page_size: 1,
    });
    expect(
      await screen.findByRole("heading", { name: "Example Registry Company" }),
    ).toBeVisible();
    const record = screen.getByRole("article");
    expect(within(record).getByText("Government sourced")).toBeVisible();
    expect(
      within(record).getAllByText("U12345DL2001PLC123456"),
    ).toHaveLength(2);
    expect(within(record).getAllByText("DL")).toHaveLength(2);
    expect(within(record).getByText("OptionalSourceField")).toBeVisible();
    expect(within(record).getByText("null")).toBeVisible();
    expect(within(record).getByText("Normalized source fields")).toBeVisible();
    expect(within(record).getByText("2001-01-01")).toBeVisible();
    expect(within(record).getByText(/Retrieved at 2026-10-22T07:52:45Z/)).toBeVisible();
    expect(
      screen.getByText(/Licence and API quota clarification is pending/),
    ).toBeVisible();
    expect(
      screen.getAllByText(/Government of India, Ministry of Corporate Affairs/),
    ).toHaveLength(2);
    expect(
      screen.getByRole("link", { name: "View dataset resource" }),
    ).toHaveAttribute("href", governmentResponse().attribution.endpoint);
    expect(
      screen.queryByRole("button", { name: /import|save|create lead/i }),
    ).not.toBeInTheDocument();
  });

  it("paginates using backend offsets and supports returning to the previous page", async () => {
    const user = userEvent.setup();
    runtimeMock.mockResolvedValue(
      configuration({ government_company_discovery_available: true }),
    );
    searchMock
      .mockResolvedValueOnce(governmentResponse())
      .mockResolvedValueOnce(
        governmentResponse({
          items: [{ CIN: "SECOND", CompanyName: "Second Source Company" }],
          offset: 1,
          has_more: true,
          next_offset: 2,
        }),
      )
      .mockResolvedValueOnce(governmentResponse());
    render(<GovernmentCompanyDiscovery />);

    await screen.findByRole("button", { name: "Search government records" });
    await user.type(screen.getByLabelText("CompanyStateCode"), "DL");
    await user.selectOptions(screen.getByLabelText("Records per page"), "10");
    await user.click(
      screen.getByRole("button", { name: "Search government records" }),
    );
    await user.click(await screen.findByRole("button", { name: "Next" }));
    expect(
      await screen.findByRole("heading", { name: "Second Source Company" }),
    ).toBeVisible();
    expect(searchMock).toHaveBeenNthCalledWith(2, {
      state_code: "DL",
      offset: 1,
      page_size: 10,
    });

    await user.click(screen.getByRole("button", { name: "Previous" }));
    expect(
      await screen.findByRole("heading", { name: "Example Registry Company" }),
    ).toBeVisible();
    expect(searchMock).toHaveBeenNthCalledWith(3, {
      state_code: "DL",
      offset: 0,
      page_size: 10,
    });
  });

  it("shows loading, empty, and safe error states", async () => {
    const user = userEvent.setup();
    runtimeMock.mockResolvedValue(
      configuration({ government_company_discovery_available: true }),
    );
    let finishSearch:
      ((value: GovernmentCompanyDiscoveryResponse) => void) | undefined;
    searchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishSearch = resolve;
        }),
    );
    render(<GovernmentCompanyDiscovery />);

    await screen.findByRole("button", { name: "Search government records" });
    await user.type(screen.getByLabelText("CompanyStateCode"), "DL");
    await user.click(
      screen.getByRole("button", { name: "Search government records" }),
    );
    expect(
      screen.getByText("Loading government company records…"),
    ).toBeVisible();
    finishSearch?.(
      governmentResponse({ items: [], has_more: false, next_offset: null }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "No government company records found",
      }),
    ).toBeVisible();
  });

  it("renders a safe provider error without exposing upstream details", async () => {
    const user = userEvent.setup();
    runtimeMock.mockResolvedValue(
      configuration({ government_company_discovery_available: true }),
    );
    searchMock.mockRejectedValue(
      new ApiError("Request failed: 503", 503, {
        detail: "private upstream error",
      }),
    );
    render(<GovernmentCompanyDiscovery />);

    await screen.findByRole("button", { name: "Search government records" });
    await user.type(screen.getByLabelText("CompanyStateCode"), "DL");
    await user.click(
      screen.getByRole("button", { name: "Search government records" }),
    );

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(
      "Government company discovery is unavailable.",
    );
    expect(alert).not.toHaveTextContent("private upstream error");
  });
});
