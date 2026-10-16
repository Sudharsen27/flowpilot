import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProspectDiscoveryPage from "@/app/(app)/prospect-discovery/page";
import { ApiError } from "@/lib/api/client";
import { previewProspectCsv } from "@/lib/api/prospect-discovery";
import type { ProspectPreviewResponse } from "@/types/api";

vi.mock("@/lib/api/prospect-discovery", () => ({
  previewProspectCsv: vi.fn(),
}));

const previewMock = vi.mocked(previewProspectCsv);

const preview: ProspectPreviewResponse = {
  columns: [
    { index: 0, label: "Company Name", field: "company" },
    { index: 1, label: "Email", field: "email" },
    { index: 2, label: "Contact", field: "name" },
  ],
  issues: [
    {
      code: "unknown_header",
      message: "Column 'Territory' is not a supported lead field and will not be used.",
      row_number: 1,
      field: null,
      severity: "warning",
    },
  ],
  rows: [
    {
      row_number: 2,
      cells: ["Acme", "ada@example.com", "Ada"],
      valid: true,
      errors: [],
      duplicate_reasons: ["EXISTING_EMAIL"],
      duplicate_of_row: null,
    },
    {
      row_number: 3,
      cells: ["Beta", "bad-email", "Bea"],
      valid: false,
      errors: [
        {
          code: "invalid_email",
          message: "Enter a valid email address.",
          row_number: 3,
          field: "email",
          severity: "error",
        },
      ],
      duplicate_reasons: [],
      duplicate_of_row: null,
    },
  ],
  summary: { total_rows: 2, valid_rows: 1, invalid_rows: 1, duplicate_rows: 1 },
};

describe("Prospect Discovery page", () => {
  beforeEach(() => {
    previewMock.mockReset();
  });

  it("shows an empty state, read-only notice, and no import action", () => {
    render(<ProspectDiscoveryPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Prospect Discovery" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "No preview yet" })).toBeVisible();
    expect(screen.getByText(/does not save prospects to the CRM/i)).toBeVisible();
    expect(screen.queryByRole("button", { name: /import/i })).not.toBeInTheDocument();
  });

  it("uploads a selected CSV and shows validation and duplicate results", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue(preview);
    render(<ProspectDiscoveryPage />);
    const file = new File(["Company Name,Email,Contact\nAcme,ada@example.com,Ada"], "prospects.csv", {
      type: "text/csv",
    });

    await user.upload(screen.getByLabelText("Choose CSV file"), file);
    expect(screen.getByText("prospects.csv")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));

    expect(previewMock).toHaveBeenCalledWith(file);
    expect(screen.getByText("Rows").nextElementSibling).toHaveTextContent("2");
    expect(screen.getAllByText("Valid")[0]?.nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Enter a valid email address.")).toBeVisible();
    expect(screen.getByText("Email matches a lead in this organization")).toBeVisible();
    expect(screen.getByText(/Column 'Territory' is not a supported lead field/)).toBeVisible();
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: /Company Name/ })).toBeVisible();
    expect(within(table).getByRole("rowheader", { name: "2" })).toBeVisible();
    expect(screen.queryByRole("button", { name: /import/i })).not.toBeInTheDocument();
  });

  it("rejects unsupported and oversized files before sending them", async () => {
    const user = userEvent.setup();
    render(<ProspectDiscoveryPage />);
    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File(["text"], "prospects.csv", { type: "text/plain" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("file type is not supported");

    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv", { type: "text/csv" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("2 MiB or smaller");
    expect(previewMock).not.toHaveBeenCalled();
  });

  it("shows loading state and a recoverable request error", async () => {
    const user = userEvent.setup();
    let finishRequest: ((value: ProspectPreviewResponse) => void) | undefined;
    previewMock
      .mockImplementationOnce(
        () => new Promise((resolve) => { finishRequest = resolve; }),
      )
      .mockRejectedValueOnce(new ApiError("Request failed", 503, { detail: "Service unavailable" }))
      .mockResolvedValueOnce(preview);
    render(<ProspectDiscoveryPage />);
    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File(["Name\nAda"], "prospects.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));
    expect(screen.getByRole("status")).toHaveTextContent("Reading and validating");
    finishRequest?.(preview);
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Preview again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Service unavailable");
    await user.click(screen.getByRole("button", { name: "Retry preview" }));
    await waitFor(() => expect(screen.getByRole("table")).toBeVisible());
  });
});