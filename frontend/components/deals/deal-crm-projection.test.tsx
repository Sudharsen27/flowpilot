import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DealCrmProjection } from "@/components/deals/deal-crm-projection";
import { getCrmCompany, type CrmCompanyDetail } from "@/lib/api/crm-companies";
import {
  listCrmContacts,
  type CrmContact,
  type CrmContactListParams,
  type CrmContactListResponse,
} from "@/lib/api/crm-contacts";

vi.mock("@/lib/api/crm-contacts", () => ({
  listCrmContacts: vi.fn(),
}));

vi.mock("@/lib/api/crm-companies", () => ({
  getCrmCompany: vi.fn(),
}));

const listCrmContactsMock = vi.mocked(listCrmContacts);
const getCrmCompanyMock = vi.mocked(getCrmCompany);

function contact(overrides: Partial<CrmContact> = {}): CrmContact {
  return {
    id: "contact-1",
    display_name: "Grace Hopper",
    first_name: "Grace",
    last_name: "Hopper",
    job_title: "Engineering Director",
    email: "grace@example.com",
    phone: "+1 555 0101",
    mobile: null,
    linkedin_url: null,
    company_id: null,
    owner_user_id: "user-1",
    source: "MANUAL",
    status: "ACTIVE",
    description: null,
    revision: 1,
    archived_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

function company(overrides: Partial<CrmCompanyDetail> = {}): CrmCompanyDetail {
  return {
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
    lifecycle_status: "PROSPECT",
    source: "MANUAL",
    owner_user_id: null,
    revision: 1,
    archived_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

function page(
  items: CrmContact[],
  total = items.length,
  offset = 0,
): CrmContactListResponse {
  return { items, limit: 100, offset, total };
}

function renderProjection(leadId: string | null = "lead-1") {
  return render(<DealCrmProjection leadId={leadId} />);
}

describe("Deal CRM projection", () => {
  beforeEach(() => {
    listCrmContactsMock.mockReset();
    getCrmCompanyMock.mockReset();
    listCrmContactsMock.mockResolvedValue(page([]));
    getCrmCompanyMock.mockImplementation(async (companyId) =>
      company({ id: companyId }),
    );
  });

  it("shows a clear no-Lead state without making CRM requests", () => {
    renderProjection(null);

    expect(
      screen.getByText("No Lead is associated with this Deal."),
    ).toBeVisible();
    expect(listCrmContactsMock).not.toHaveBeenCalled();
    expect(getCrmCompanyMock).not.toHaveBeenCalled();
  });

  it("shows an empty state when the Lead has no Contacts", async () => {
    renderProjection();

    expect(
      await screen.findByText("No CRM Contacts are associated with this Lead."),
    ).toBeVisible();
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      {
        leadId: "lead-1",
        includeArchived: true,
        limit: 100,
        offset: 0,
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getCrmCompanyMock).not.toHaveBeenCalled();
  });

  it("shows one Contact and its CRM Company", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([contact({ company_id: "company-1" })]),
    );

    renderProjection();

    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("fetches a shared Company only once for multiple Contacts", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([
        contact({ company_id: "company-1" }),
        contact({
          id: "contact-2",
          display_name: "Katherine Johnson",
          company_id: "company-1",
        }),
      ]),
    );

    renderProjection();

    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    expect(await screen.findByText("Katherine Johnson")).toBeVisible();
    expect(await screen.findAllByText("CRM Company: Acme CRM")).toHaveLength(2);
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(1);
  });

  it("fetches distinct Companies once each", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([
        contact({ company_id: "company-1" }),
        contact({
          id: "contact-2",
          display_name: "Katherine Johnson",
          company_id: "company-2",
        }),
      ]),
    );
    getCrmCompanyMock.mockImplementation(async (companyId) =>
      company({
        id: companyId,
        name: companyId === "company-1" ? "Acme CRM" : "Globex CRM",
      }),
    );

    renderProjection();

    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(await screen.findByText("CRM Company: Globex CRM")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(2);
    expect(getCrmCompanyMock).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(getCrmCompanyMock).toHaveBeenCalledWith(
      "company-2",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("labels archived Contacts and Companies", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([
        contact({
          archived_at: "2026-09-12T10:00:00Z",
          company_id: "company-1",
        }),
      ]),
    );
    getCrmCompanyMock.mockResolvedValue(
      company({ archived_at: "2026-09-13T10:00:00Z" }),
    );

    renderProjection();

    expect(await screen.findByText("Archived Contact")).toBeVisible();
    expect(await screen.findByText("Archived Company")).toBeVisible();
    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
  });

  it("aborts pending Company requests and ignores stale results after a Lead change", async () => {
    let companySignal: AbortSignal | undefined;
    let resolveCompany!: (response: CrmCompanyDetail) => void;
    listCrmContactsMock.mockImplementation(async ({ leadId } = {}) =>
      page([
        leadId === "lead-1"
          ? contact({
              display_name: "Lead One Contact",
              company_id: "company-1",
            })
          : contact({
              id: "contact-2",
              display_name: "Lead Two Contact",
            }),
      ]),
    );
    getCrmCompanyMock.mockImplementation((_companyId, options) => {
      companySignal = options?.signal;
      return new Promise((resolve) => {
        resolveCompany = resolve;
      });
    });

    const { rerender } = renderProjection("lead-1");

    expect(await screen.findByText("Lead One Contact")).toBeVisible();
    await waitFor(() => expect(getCrmCompanyMock).toHaveBeenCalledTimes(1));
    expect(companySignal?.aborted).toBe(false);

    rerender(<DealCrmProjection leadId="lead-2" />);
    expect(await screen.findByText("Lead Two Contact")).toBeVisible();
    expect(companySignal?.aborted).toBe(true);

    await act(async () =>
      resolveCompany(company({ name: "Lead One Company" })),
    );
    expect(
      screen.queryByText("CRM Company: Lead One Company"),
    ).not.toBeInTheDocument();
  });

  it("does not reuse cached Company data when switching Leads", async () => {
    listCrmContactsMock.mockImplementation(async ({ leadId } = {}) =>
      page([
        contact({
          id: leadId === "lead-1" ? "contact-1" : "contact-2",
          display_name:
            leadId === "lead-1" ? "Lead One Contact" : "Lead Two Contact",
          company_id: "company-1",
        }),
      ]),
    );
    getCrmCompanyMock
      .mockResolvedValueOnce(company({ name: "Lead One Company" }))
      .mockResolvedValueOnce(company({ name: "Lead Two Company" }));

    const { rerender } = renderProjection("lead-1");

    expect(
      await screen.findByText("CRM Company: Lead One Company"),
    ).toBeVisible();
    rerender(<DealCrmProjection leadId="lead-2" />);

    expect(await screen.findByText("Lead Two Contact")).toBeVisible();
    expect(
      await screen.findByText("CRM Company: Lead Two Company"),
    ).toBeVisible();
    expect(
      screen.queryByText("CRM Company: Lead One Company"),
    ).not.toBeInTheDocument();
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(2);
    expect(getCrmCompanyMock).toHaveBeenNthCalledWith(
      2,
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("paginates all Contacts in 100-item pages", async () => {
    const user = userEvent.setup();
    const contacts = Array.from({ length: 101 }, (_, index) =>
      contact({
        id: `contact-${index + 1}`,
        display_name: `Contact ${index + 1}`,
        company_id: index === 0 || index === 100 ? "company-1" : null,
      }),
    );
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        page(
          contacts.slice(params.offset ?? 0, (params.offset ?? 0) + 100),
          contacts.length,
          params.offset ?? 0,
        ),
    );

    renderProjection();

    expect(await screen.findByText("Contact 1")).toBeVisible();
    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(screen.getByText("1–100 of 101")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(1);
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 100, offset: 0 }),
      expect.anything(),
    );
    await user.click(screen.getByRole("button", { name: "Next Contacts" }));
    expect(await screen.findByText("Contact 101")).toBeVisible();
    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(screen.getByText("101–101 of 101")).toBeVisible();
    expect(listCrmContactsMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 100, offset: 100 }),
      expect.anything(),
    );
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(1);
  });

  it("limits simultaneous Company lookups", async () => {
    const contacts = Array.from({ length: 8 }, (_, index) =>
      contact({
        id: `contact-${index + 1}`,
        display_name: `Contact ${index + 1}`,
        company_id: `company-${index + 1}`,
      }),
    );
    const resolvers = new Map<string, (response: CrmCompanyDetail) => void>();
    listCrmContactsMock.mockResolvedValue(page(contacts));
    getCrmCompanyMock.mockImplementation(
      (companyId) =>
        new Promise((resolve) => {
          resolvers.set(companyId, resolve);
        }),
    );

    renderProjection();

    await waitFor(() => expect(getCrmCompanyMock).toHaveBeenCalledTimes(5));
    expect(resolvers.size).toBe(5);
    for (let count = 0; count < contacts.length; count += 1) {
      await waitFor(() => expect(resolvers.size).toBeGreaterThan(0));
      const [companyId, resolve] = Array.from(resolvers.entries())[0]!;
      await act(async () => resolve(company({ id: companyId })));
      resolvers.delete(companyId);
    }
    await waitFor(() => expect(getCrmCompanyMock).toHaveBeenCalledTimes(8));
    expect(await screen.findAllByText(/CRM Company: Acme CRM/)).toHaveLength(8);
  });

  it("shows loading, errors, and retries Contact requests", async () => {
    const user = userEvent.setup();
    let resolveContacts!: (response: CrmContactListResponse) => void;
    listCrmContactsMock.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveContacts = resolve;
      }),
    );

    renderProjection();

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading CRM Contacts",
    );
    resolveContacts(page([contact()]));
    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    listCrmContactsMock.mockRejectedValueOnce(new Error("network"));

    const { unmount } = renderProjection("lead-2");
    expect(
      await screen.findByText("CRM Contacts could not be loaded"),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Retry CRM Contacts" }),
    );
    expect(
      await screen.findByText("No CRM Contacts are associated with this Lead."),
    ).toBeVisible();
    unmount();
  });

  it("keeps Contacts visible and retries a failed Company lookup", async () => {
    const user = userEvent.setup();
    listCrmContactsMock.mockResolvedValue(
      page([contact({ company_id: "company-1" })]),
    );
    getCrmCompanyMock
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce(company());

    renderProjection();

    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    expect(
      await screen.findByText("CRM Company details unavailable"),
    ).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Contacts are still shown.",
    );
    await user.click(
      screen.getByRole("button", { name: "Retry Company lookups" }),
    );
    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(2);
  });

  it("aborts pending Contact requests when the Lead changes or unmounts", async () => {
    let firstSignal: AbortSignal | undefined;
    let resolveFirst!: (response: CrmContactListResponse) => void;
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}, options) => {
        if (params.leadId === "lead-1") {
          firstSignal = options?.signal;
          return new Promise((resolve) => {
            resolveFirst = resolve;
          });
        }
        return page([contact({ id: "contact-2", display_name: "Lead Two" })]);
      },
    );
    const { rerender, unmount } = renderProjection("lead-1");

    await waitFor(() => expect(listCrmContactsMock).toHaveBeenCalledTimes(1));
    rerender(<DealCrmProjection leadId="lead-2" />);
    expect(await screen.findByText("Lead Two")).toBeVisible();
    expect(firstSignal?.aborted).toBe(true);

    resolveFirst(page([contact({ display_name: "Stale Lead One" })]));
    expect(screen.queryByText("Stale Lead One")).not.toBeInTheDocument();

    listCrmContactsMock.mockImplementation(async (_params, options) => {
      firstSignal = options?.signal;
      return new Promise(() => {});
    });
    rerender(<DealCrmProjection leadId="lead-3" />);
    await waitFor(() =>
      expect(listCrmContactsMock).toHaveBeenCalledWith(
        expect.objectContaining({ leadId: "lead-3" }),
        expect.anything(),
      ),
    );
    unmount();
    expect(firstSignal?.aborted).toBe(true);
  });

  it("does not display legacy Lead company text as a CRM Company", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([contact({ company_id: "company-1" })]),
    );

    renderProjection();

    expect(await screen.findByText("CRM Company: Acme CRM")).toBeVisible();
    expect(screen.queryByText(/Legacy/)).not.toBeInTheDocument();
  });
});
