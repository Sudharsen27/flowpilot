import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProspectDiscoveryPage from "@/app/(app)/prospect-discovery/page";
import { ApiError } from "@/lib/api/client";
import { searchProspects } from "@/lib/api/prospect-discovery";
import type {
  ProspectDiscoverySearchRequest,
  ProspectDiscoverySearchResponse,
} from "@/types/api";

vi.mock("@/lib/api/prospect-discovery", () => ({
  searchProspects: vi.fn(),
}));

const searchMock = vi.mocked(searchProspects);

const business = {
  name: "Kitepath Software",
  industry: "Software",
  country: "United States",
  region: "New York",
  employee_count: 22,
  description: "Develops planning software for distributed teams.",
  synthetic: true,
  verification_status: "SYNTHETIC_UNVERIFIED",
  match_explanations: ["Industry matches Software.", "Geography matches United States."],
} satisfies ProspectDiscoverySearchResponse["items"][number];

function response(
  overrides: Partial<ProspectDiscoverySearchResponse> = {},
): ProspectDiscoverySearchResponse {
  return {
    source: "SYNTHETIC",
    items: [business],
    page_size: 10,
    has_more: false,
    next_cursor: null,
    ...overrides,
  };
}

describe("Discovery Workspace", () => {
  beforeEach(() => {
    searchMock.mockReset();
  });

  it("renders accessible supported filters and explains the synthetic-only data", () => {
    render(<ProspectDiscoveryPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Discovery Workspace" }),
    ).toBeVisible();
    expect(screen.getByRole("region", { name: "Search filters" })).toBeVisible();
    expect(screen.getByLabelText("Industry")).toBeVisible();
    expect(screen.getByLabelText("Country")).toBeVisible();
    expect(screen.getByRole("combobox", { name: /Region/ })).toBeDisabled();
    expect(screen.getByLabelText("Minimum employees")).toBeVisible();
    expect(screen.getByLabelText("Maximum employees")).toBeVisible();
    expect(screen.getByLabelText("Results per page")).toBeVisible();
    expect(screen.getByLabelText("Synthetic data notice")).toHaveTextContent(
      "not verified real companies",
    );
    expect(screen.getByText(/fixed demo dataset/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Import unavailable" })).toBeDisabled();
    expect(screen.getByText(/No discovery results can be saved/)).toBeVisible();
    expect(searchMock).not.toHaveBeenCalled();
  });

  it("submits normalized supported filters through the discovery API", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(response());
    render(<ProspectDiscoveryPage />);

    await user.selectOptions(screen.getByLabelText("Industry"), "Software");
    await user.selectOptions(screen.getByLabelText("Country"), "United States");
    await user.selectOptions(screen.getByRole("combobox", { name: /Region/ }), "New York");
    await user.type(screen.getByLabelText("Minimum employees"), "10");
    await user.type(screen.getByLabelText("Maximum employees"), "250");
    await user.selectOptions(screen.getByLabelText("Results per page"), "5");
    await user.click(screen.getByRole("button", { name: "Search businesses" }));

    expect(searchMock).toHaveBeenCalledWith({
      industry: "Software",
      country: "United States",
      region: "New York",
      minimum_employees: 10,
      maximum_employees: 250,
      page_size: 5,
    });
    expect(await screen.findByText("Kitepath Software")).toBeVisible();
  });

  it("shows field-level range validation and does not call the API", async () => {
    const user = userEvent.setup();
    render(<ProspectDiscoveryPage />);

    await user.type(screen.getByLabelText("Minimum employees"), "50");
    await user.type(screen.getByLabelText("Maximum employees"), "10");
    await user.click(screen.getByRole("button", { name: "Search businesses" }));

    expect(screen.getByText("Minimum employees cannot exceed maximum.")).toBeVisible();
    expect(screen.getByText("Maximum employees must be at least the minimum.")).toBeVisible();
    expect(searchMock).not.toHaveBeenCalled();
  });

  it("resets all filters and clears prior results", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(response());
    render(<ProspectDiscoveryPage />);

    await user.selectOptions(screen.getByLabelText("Industry"), "Software");
    await user.type(screen.getByLabelText("Minimum employees"), "10");
    await user.click(screen.getByRole("button", { name: "Search businesses" }));
    expect(await screen.findByText("Kitepath Software")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Reset filters" }));

    expect(screen.getByLabelText("Industry")).toHaveValue("");
    expect(screen.getByLabelText("Minimum employees")).toHaveValue(null);
    expect(screen.queryByText("Kitepath Software")).not.toBeInTheDocument();
    expect(searchMock).toHaveBeenCalledTimes(1);
  });

  it("shows loading feedback and prevents duplicate submissions", async () => {
    const user = userEvent.setup();
    let finishSearch: ((value: ProspectDiscoverySearchResponse) => void) | undefined;
    searchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishSearch = resolve;
        }),
    );
    render(<ProspectDiscoveryPage />);

    const searchButton = screen.getByRole("button", { name: "Search businesses" });
    await user.click(searchButton);
    expect(screen.getByRole("status", { name: "Loading synthetic businesses" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Searching…" }));
    expect(searchMock).toHaveBeenCalledTimes(1);

    finishSearch?.(response());
    expect(await screen.findByText("Kitepath Software")).toBeVisible();
  });

  it("renders synthetic status and filter explanations without a fabricated fit score", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(response());
    render(<ProspectDiscoveryPage />);

    await user.click(screen.getByRole("button", { name: "Search businesses" }));

    const result = await screen.findByRole("article");
    expect(within(result).getByText("Synthetic · unverified")).toBeVisible();
    expect(within(result).getByText("22")).toBeVisible();
    expect(within(result).getByText("Develops planning software for distributed teams.")).toBeVisible();
    expect(within(result).getByText("Industry matches Software.")).toBeVisible();
    expect(within(result).getByText(/Filter explanations only/)).toBeVisible();
    expect(within(result).queryByText(/Strong|Moderate|Weak|confidence/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import unavailable" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: /create lead|save prospect/i })).not.toBeInTheDocument();
    expect(searchMock).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state using the server result", async () => {
    const user = userEvent.setup();
    searchMock.mockResolvedValue(response({ items: [], has_more: false }));
    render(<ProspectDiscoveryPage />);

    await user.click(screen.getByRole("button", { name: "Search businesses" }));

    expect(await screen.findByRole("heading", { name: "No synthetic businesses matched" })).toBeVisible();
    expect(screen.getByText(/does not represent comprehensive real-world coverage/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
  });

  it("uses the server cursor unchanged and preserves filters on the next page", async () => {
    const user = userEvent.setup();
    const cursor = "eyJwYWdlIjoxfQ.signature-as-returned";
    searchMock
      .mockResolvedValueOnce(response({ has_more: true, next_cursor: cursor }))
      .mockResolvedValueOnce(
        response({
          items: [{ ...business, name: "Second Synthetic Business" }],
        }),
      );
    render(<ProspectDiscoveryPage />);

    await user.selectOptions(screen.getByLabelText("Industry"), "Software");
    await user.selectOptions(screen.getByLabelText("Results per page"), "5");
    await user.click(screen.getByRole("button", { name: "Search businesses" }));
    expect(await screen.findByRole("button", { name: "Next page" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Next page" }));

    expect(searchMock).toHaveBeenNthCalledWith(2, {
      industry: "Software",
      page_size: 5,
      cursor,
    });
    expect(await screen.findByText("Second Synthetic Business")).toBeVisible();
  });

  it("starts a changed search without reusing the previous page cursor", async () => {
    const user = userEvent.setup();
    const cursor = "opaque-signed-cursor";
    searchMock
      .mockResolvedValueOnce(response({ has_more: true, next_cursor: cursor }))
      .mockResolvedValueOnce(response());
    render(<ProspectDiscoveryPage />);

    await user.click(screen.getByRole("button", { name: "Search businesses" }));
    await screen.findByRole("button", { name: "Next page" });
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await screen.findByText("Kitepath Software");

    await user.selectOptions(screen.getByLabelText("Industry"), "Healthcare");
    expect(screen.queryByRole("button", { name: "Next page" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Search businesses" }));

    expect(searchMock).toHaveBeenNthCalledWith(3, {
      industry: "Healthcare",
      page_size: 10,
    } satisfies ProspectDiscoverySearchRequest);
  });

  it("shows a safe usage-limit error and supports retry", async () => {
    const user = userEvent.setup();
    searchMock
      .mockRejectedValueOnce(
        new ApiError("Request failed: 429", 429, {
          detail: "Sensitive internal limiter detail",
        }),
      )
      .mockResolvedValueOnce(response());
    render(<ProspectDiscoveryPage />);

    await user.click(screen.getByRole("button", { name: "Search businesses" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The organization’s discovery usage limit has been reached. Try again later.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("Sensitive internal");
    await user.click(screen.getByRole("button", { name: "Retry search" }));
    expect(await screen.findByText("Kitepath Software")).toBeVisible();
  });

  it("ignores stale results after resetting an in-flight request", async () => {
    const user = userEvent.setup();
    let finishSearch: ((value: ProspectDiscoverySearchResponse) => void) | undefined;
    searchMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          finishSearch = resolve;
        }),
    );
    render(<ProspectDiscoveryPage />);

    await user.click(screen.getByRole("button", { name: "Search businesses" }));
    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    finishSearch?.(response());

    expect(await screen.findByText(/Choose any supported filters/)).toBeVisible();
    expect(screen.queryByText("Kitepath Software")).not.toBeInTheDocument();
  });
});
