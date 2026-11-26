import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ContactDetailPage from "@/app/(app)/contacts/[id]/page";
import { ApiError } from "@/lib/api/client";
import { getCrmCompany, type CrmCompanyDetail } from "@/lib/api/crm-companies";
import { getCrmContact, type CrmContact } from "@/lib/api/crm-contacts";

const route = vi.hoisted(() => ({ id: "contact-1" }));

vi.mock("next/navigation", () => ({
  useParams: () => route,
}));

vi.mock("@/lib/api/crm-contacts", () => ({
  getCrmContact: vi.fn(),
}));

vi.mock("@/lib/api/crm-companies", () => ({
  getCrmCompany: vi.fn(),
}));

const getContactMock = vi.mocked(getCrmContact);
const getCompanyMock = vi.mocked(getCrmCompany);

function contact(overrides: Partial<CrmContact> = {}): CrmContact {
  return {
    id: "contact-1",
    display_name: "Grace Hopper",
    first_name: "Grace",
    last_name: "Hopper",
    job_title: "Engineering Director",
    email: "grace@example.com",
    phone: "+1 555 0101",
    mobile: "+1 555 0102",
    linkedin_url: "https://linkedin.example/grace",
    company_id: "company-1",
    owner_user_id: "user-1",
    source: "MANUAL",
    status: "ACTIVE",
    description: "Contact description",
    revision: 3,
    archived_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

const company: CrmCompanyDetail = {
  id: "company-1",
  name: "Acme CRM",
  website_domain: "acme.example",
  industry: null,
  employee_count: null,
  phone: null,
  email: null,
  address_line1: null,
  address_line2: null,
  city: null,
  region: null,
  postal_code: null,
  country: null,
  description: null,
  lifecycle_status: "CUSTOMER",
  source: "MANUAL",
  owner_user_id: "user-2",
  revision: 1,
  archived_at: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

describe("ContactDetailPage", () => {
  beforeEach(() => {
    route.id = "contact-1";
    getContactMock.mockReset();
    getContactMock.mockResolvedValue(contact());
    getCompanyMock.mockReset();
    getCompanyMock.mockResolvedValue(company);
  });

  it("shows loading state, then Contact details and associated Company", async () => {
    let resolveContact!: (value: CrmContact) => void;
    getContactMock.mockImplementationOnce(
      () =>
        new Promise<CrmContact>((resolve) => {
          resolveContact = resolve;
        }),
    );

    render(<ContactDetailPage />);

    expect(
      screen.getByRole("heading", { name: "Loading Contact" }),
    ).toBeVisible();
    await act(async () => resolveContact(contact()));

    expect(
      await screen.findByRole("heading", { name: "Grace Hopper" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "grace@example.com" }),
    ).toHaveAttribute("href", "mailto:grace@example.com");
    expect(screen.getByRole("link", { name: "+1 555 0101" })).toHaveAttribute(
      "href",
      "tel:+1 555 0101",
    );
    expect(
      await screen.findByRole("link", { name: "Acme CRM" }),
    ).toHaveAttribute("href", "/companies/company-1");
    expect(screen.getByText("user-1")).toBeVisible();
    expect(screen.getAllByText("Active")).toHaveLength(2);
    expect(getContactMock).toHaveBeenCalledWith(
      "contact-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getCompanyMock).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("shows a not-found state for a tenant-scoped 404 response", async () => {
    getContactMock.mockRejectedValue(new ApiError("missing", 404));

    render(<ContactDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Contact not found" }),
    ).toBeVisible();
    expect(
      screen.getByText(
        "The Contact may have been removed or may not be available in your organization.",
      ),
    ).toBeVisible();
  });

  it("shows a retryable state for API errors", async () => {
    const user = userEvent.setup();
    getContactMock
      .mockRejectedValueOnce(new ApiError("unavailable", 503))
      .mockResolvedValueOnce(contact());

    render(<ContactDetailPage />);

    expect(
      await screen.findByRole("heading", { name: "Contact unavailable" }),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(getContactMock).toHaveBeenCalledTimes(2));
    expect(
      await screen.findByRole("heading", { name: "Grace Hopper" }),
    ).toBeVisible();
  });

  it("aborts the Contact request when unmounted", async () => {
    let requestSignal: AbortSignal | undefined;
    getContactMock.mockImplementationOnce(
      (_contactId, options) =>
        new Promise<CrmContact>(() => {
          requestSignal = options?.signal;
        }),
    );

    const view = render(<ContactDetailPage />);
    await waitFor(() => expect(requestSignal).toBeDefined());

    expect(requestSignal?.aborted).toBe(false);
    view.unmount();
    expect(requestSignal?.aborted).toBe(true);
  });

  it("shows an Archived indicator and timestamp for an archived Contact", async () => {
    getContactMock.mockResolvedValueOnce(
      contact({ archived_at: "2026-09-20T12:34:56Z" }),
    );

    render(<ContactDetailPage />);

    expect(await screen.findAllByText("Archived")).toHaveLength(2);
    expect(screen.getByText("2026-09-20 12:34:56 UTC")).toBeVisible();
  });

  it("does not render a previous Contact when the route ID changes", async () => {
    let resolveFirst!: (value: CrmContact) => void;
    let resolveSecond!: (value: CrmContact) => void;
    getContactMock.mockImplementation(
      (id) =>
        new Promise<CrmContact>((resolve) => {
          if (id === "contact-1") resolveFirst = resolve;
          else resolveSecond = resolve;
        }),
    );

    const view = render(<ContactDetailPage />);
    await waitFor(() =>
      expect(getContactMock).toHaveBeenCalledWith(
        "contact-1",
        expect.anything(),
      ),
    );

    route.id = "contact-2";
    view.rerender(<ContactDetailPage />);
    await act(async () =>
      resolveSecond(
        contact({ id: "contact-2", display_name: "Katherine Johnson" }),
      ),
    );

    expect(
      await screen.findByRole("heading", { name: "Katherine Johnson" }),
    ).toBeVisible();
    await act(async () => resolveFirst(contact()));
    expect(screen.queryByRole("heading", { name: "Grace Hopper" })).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Katherine Johnson" }),
    ).toBeVisible();
  });
});
