import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProspectDiscoveryPage from "@/app/(app)/prospect-discovery/page";
import { ApiError } from "@/lib/api/client";
import { importProspectCsv, previewProspectCsv } from "@/lib/api/prospect-discovery";
import type { ProspectImportResponse, ProspectPreviewResponse } from "@/types/api";

vi.mock("@/lib/api/prospect-discovery", () => ({
  importProspectCsv: vi.fn(),
  previewProspectCsv: vi.fn(),
}));

const importMock = vi.mocked(importProspectCsv);
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

const eligiblePreview: ProspectPreviewResponse = {
  columns: [
    { index: 0, label: "Name", field: "name" },
    { index: 1, label: "Email", field: "email" },
  ],
  issues: [],
  rows: [
    {
      row_number: 2,
      cells: ["Ada", "ada@example.com"],
      valid: true,
      errors: [],
      duplicate_reasons: [],
      duplicate_of_row: null,
    },
  ],
  summary: { total_rows: 1, valid_rows: 1, invalid_rows: 0, duplicate_rows: 0 },
};

const successfulImport: ProspectImportResponse = {
  total_rows: 1,
  imported_count: 1,
  skipped_count: 0,
  failed_count: 0,
  rows: [
    {
      row_number: 2,
      status: "IMPORTED",
      reason_code: null,
      message: null,
      duplicate_of_row: null,
    },
  ],
};

describe("Prospect Discovery page", () => {
  beforeEach(() => {
    importMock.mockReset();
    previewMock.mockReset();
  });

  it("shows an empty state without an import action before preview", () => {
    render(<ProspectDiscoveryPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Prospect Discovery" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "No preview yet" })).toBeVisible();
    expect(screen.getByText(/review every row before confirming an import/i)).toBeVisible();
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
    expect(
      screen.getByRole("button", { name: "Import 0 eligible leads" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/2 invalid or duplicate rows will be skipped/i),
    ).toBeVisible();
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
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "large.csv", {
        type: "text/csv",
      }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("2 MiB or smaller");
    expect(previewMock).not.toHaveBeenCalled();
  });

  it("shows loading state and a recoverable request error", async () => {
    const user = userEvent.setup();
    let finishRequest: ((value: ProspectPreviewResponse) => void) | undefined;
    previewMock
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishRequest = resolve;
          }),
      )
      .mockRejectedValueOnce(
        new ApiError("Request failed", 503, { detail: "Service unavailable" }),
      )
      .mockResolvedValueOnce(preview);
    render(<ProspectDiscoveryPage />);
    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File(["Name\nAda"], "prospects.csv", { type: "text/csv" }),
    );
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));
    expect(screen.getByRole("status")).toHaveTextContent(
      "Reading and validating",
    );
    finishRequest?.(preview);
    await screen.findByRole("table");

    await user.click(screen.getByRole("button", { name: "Preview again" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Service unavailable",
    );
    await user.click(screen.getByRole("button", { name: "Retry preview" }));
    await waitFor(() => expect(screen.getByRole("table")).toBeVisible());
  });

  it("requires confirmation, prevents repeat submission, and shows successful import", async () => {
    const user = userEvent.setup();
    let finishImport: ((value: ProspectImportResponse) => void) | undefined;
    previewMock.mockResolvedValue(eligiblePreview);
    importMock.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishImport = resolve;
        }),
    );
    render(<ProspectDiscoveryPage />);
    const file = new File(
      ["Name,Email\nAda,ada@example.com"],
      "prospects.csv",
      {
        type: "text/csv",
      },
    );
    await user.upload(screen.getByLabelText("Choose CSV file"), file);
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));

    const importButton = await screen.findByRole("button", {
      name: "Import 1 eligible leads",
    });
    expect(importButton).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: /I confirm that eligible prospects/i,
      }),
    );
    expect(importButton).toBeEnabled();
    await user.click(importButton);

    expect(importMock).toHaveBeenCalledWith(file);
    expect(screen.getByText("Importing confirmed prospects…")).toBeVisible();
    expect(importButton).toBeDisabled();
    await user.click(importButton);
    expect(importMock).toHaveBeenCalledTimes(1);
    finishImport?.(successfulImport);

    expect(
      await screen.findByRole("heading", { name: "Import complete" }),
    ).toBeVisible();
    expect(screen.getByText("1 imported, 0 skipped, 0 failed.")).toBeVisible();
    expect(
      screen.getByText("This file has already been submitted."),
    ).toBeVisible();
  });

  it("shows partial-success counts and row-level skip reasons", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue(eligiblePreview);
    importMock.mockResolvedValue({
      ...successfulImport,
      total_rows: 3,
      skipped_count: 1,
      failed_count: 1,
      rows: [
        successfulImport.rows[0],
        {
          row_number: 3,
          status: "SKIPPED",
          reason_code: "EXISTING_EMAIL",
          message:
            "A lead with this email already exists in this organization.",
          duplicate_of_row: null,
        },
        {
          row_number: 4,
          status: "FAILED",
          reason_code: "CREATE_FAILED",
          message:
            "The row could not be imported. Correct it or retry after checking the CRM.",
          duplicate_of_row: null,
        },
      ],
    });
    render(<ProspectDiscoveryPage />);
    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File(["Name,Email\nAda,ada@example.com"], "prospects.csv", {
        type: "text/csv",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));
    await user.click(
      await screen.findByRole("checkbox", {
        name: /I confirm that eligible prospects/i,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Import 1 eligible leads" }),
    );

    expect(
      await screen.findByRole("heading", { name: "Partial import complete" }),
    ).toBeVisible();
    expect(screen.getByText("1 imported, 1 skipped, 1 failed.")).toBeVisible();
    expect(
      screen.getByText(
        "A lead with this email already exists in this organization.",
      ),
    ).toBeVisible();
    expect(
      screen.getByText(/Preview this file again before retrying failed rows/i),
    ).toBeVisible();
  });

  it("shows a recoverable import failure", async () => {
    const user = userEvent.setup();
    previewMock.mockResolvedValue(eligiblePreview);
    importMock.mockRejectedValue(
      new ApiError("Request failed", 503, {
        detail: "Import service unavailable",
      }),
    );
    render(<ProspectDiscoveryPage />);
    await user.upload(
      screen.getByLabelText("Choose CSV file"),
      new File(["Name,Email\nAda,ada@example.com"], "prospects.csv", {
        type: "text/csv",
      }),
    );
    await user.click(screen.getByRole("button", { name: "Preview CSV" }));
    await user.click(
      await screen.findByRole("checkbox", {
        name: /I confirm that eligible prospects/i,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Import 1 eligible leads" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Import service unavailable",
    );
    expect(
      screen.queryByRole("heading", { name: "Import complete" }),
    ).not.toBeInTheDocument();
  });
});
