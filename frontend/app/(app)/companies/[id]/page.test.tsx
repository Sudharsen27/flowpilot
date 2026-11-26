import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CompanyDetailPage from "@/app/(app)/companies/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getCrmCompany, type CrmCompanyDetail } from "@/lib/api/crm-companies";

const route = vi.hoisted(() => ({ id: "company-1" }));

vi.mock("next/navigation", () => ({
  useParams: () => route,
}));

vi.mock("@/lib/api/crm-companies", () => ({
  getCrmCompany: vi.fn(),
}));

const getCompanyMock = vi.mocked(getCrmCompany);

function company(overrides: Partial<CrmCompanyDetail> = {}): CrmCompanyDetail {
  return {
    id: "company-1",
    name: "Acme CRM",
    website_domain: "acme.example",
    lifecycle_status: "CUSTOMER",
    owner_user_id: "user-1",
    industry: "Software",
    employee_count: 100,
    phone: "+1 555 0201",
    email: "hello@acme.example",
    address_line1: "1 Main Street",
    address_line2: null,
    city: "London",
    region: null,
    postal_code: "SW1A 1AA",
    country: "United Kingdom",
    description: "Company description",
    source: "MANUAL",
    revision: 2,
    archived_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

describe("CompanyDetailPage", () => {
  beforeEach(() => {
    route.id = "company-1";
    getCompanyMock.mockReset();
    getCompanyMock.mockResolvedValue(company());
  });

  it("shows loading state, then Company details", async () => {
    let resolveCompany!: (value: CrmCompanyDetail) => void;
    getCompanyMock.mockImplementationOnce(
      () =>
        new Promise<CrmCompanyDetail>((resolve) => {
          resolveCompany = resolve;
        }),
    );

    render(<CompanyDetailPage />);

    expect(
      screen.getByRole("heading", { name: "Loading Company" }),
    ).toBeVisible();
    await act(async () => resolveCompany(company()));

    expect(
      await screen.findByRole("heading", { name: "Acme CRM" }),
    ).toBeVisible();
    expect(screen.getByText("acme.example")).toBeVisible();
    expect(screen.getAllByText("Customer")).toHaveLength(2);
    expect(screen.getByText("user-1")).toBeVisible();
    expect(screen.getByText("Software")).toBeVisible();
    expect(getCompanyMock).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a not-found state for a tenant-scoped 404 response", async () => {
    getCompanyMock.mockRejectedValue(new ApiError("missing", 404));

    render(<CompanyDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Company not found" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The Company may have been removed or may not be available in your organization.",
      ),
    ).toBeVisible();
  });

  it("shows a retryable state for API errors", async () => {
    const user = userEvent.setup();
    getCompanyMock
      .mockRejectedValueOnce(new ApiError("unavailable", 503))
      .mockResolvedValueOnce(company());

    render(<CompanyDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Company unavailable" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(getCompanyMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("heading", { name: "Acme CRM" }),
    ).toBeVisible();
  });

  it("aborts the Company request when unmounted", async () => {
    let requestSignal: AbortSignal | undefined;
    getCompanyMock.mockImplementationOnce(
      (_companyId, options) =>
        new Promise<CrmCompanyDetail>(() => {
          requestSignal = options?.signal;
        }),
    );

    const view = render(<CompanyDetailPage />);
    await waitFor(() => expect(requestSignal).toBeDefined());

    expect(requestSignal?.aborted).toBe(false);
    view.unmount();
    expect(requestSignal?.aborted).toBe(true);
  });

  it("shows an Archived indicator and timestamp for an archived Company", async () => {
    getCompanyMock.mockResolvedValueOnce(
      company({ archived_at: "2026-09-20T12:34:56Z" }),
    );

    render(<CompanyDetailPage />);

    expect(await screen.findAllByText("Archived")).toHaveLength(2);
    expect(screen.getByText("2026-09-20 12:34:56 UTC")).toBeVisible();
  });

  it("does not render a previous Company when the route ID changes", async () => {
    let resolveFirst!: (value: CrmCompanyDetail) => void;
    let resolveSecond!: (value: CrmCompanyDetail) => void;
    getCompanyMock.mockImplementation(
      (id) =>
        new Promise<CrmCompanyDetail>((resolve) => {
          if (id === "company-1") resolveFirst = resolve;
          else resolveSecond = resolve;
        }),
    );

    const view = render(<CompanyDetailPage />);
    await waitFor(() =>
      expect(getCompanyMock).toHaveBeenCalledWith(
        "company-1",
        expect.anything(),
      ),
    );

    route.id = "company-2";
    view.rerender(<CompanyDetailPage />);
    await act(async () =>
      resolveSecond(company({ id: "company-2", name: "Globex" })),
    );

    expect(
      await screen.findByRole("heading", { name: "Globex" }),
    ).toBeVisible();
    await act(async () => resolveFirst(company()));
    expect(screen.queryByRole("heading", { name: "Acme CRM" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Globex" })).toBeVisible();
  });
});
