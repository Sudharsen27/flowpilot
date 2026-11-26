import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Customer360Profile } from "@/components/leads/customer-360-profile";
import { CrmContactAssociations } from "@/components/leads/crm-contact-associations";
import { ApiError } from "@/lib/api/client";
import { getCrmCompany } from "@/lib/api/crm-companies";
import {
  listCrmContacts,
  updateCrmContactLeadLink,
  type CrmContact,
  type CrmContactListParams,
} from "@/lib/api/crm-contacts";
import type { Lead } from "@/types/api";

vi.mock("@/lib/api/crm-contacts", () => ({
  listCrmContacts: vi.fn(),
  updateCrmContactLeadLink: vi.fn(),
}));

vi.mock("@/lib/api/crm-companies", () => ({
  getCrmCompany: vi.fn(),
}));

const listCrmContactsMock = vi.mocked(listCrmContacts);
const updateCrmContactLeadLinkMock = vi.mocked(updateCrmContactLeadLink);
const getCrmCompanyMock = vi.mocked(getCrmCompany);

const lead: Lead = {
  id: "lead-1",
  name: "Ada Prospect",
  email: "ada@example.com",
  phone: "+1 555 0100",
  company: "Legacy Company",
  source: "WEBSITE",
  status: "NEW",
  enquiry: "We need a product demo.",
  notes: null,
  created_at: "2026-09-01T10:00:00Z",
  updated_at: "2026-09-10T10:00:00Z",
};

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
    revision: 3,
    archived_at: null,
    created_at: "2026-09-01T10:00:00Z",
    updated_at: "2026-09-10T10:00:00Z",
    ...overrides,
  };
}

function page(items: CrmContact[]) {
  return { items, limit: 20, offset: 0, total: items.length };
}

function renderProfile() {
  return render(<Customer360Profile lead={lead} />);
}

describe("Customer 360 profile Contact associations", () => {
  beforeEach(() => {
    listCrmContactsMock.mockReset();
    updateCrmContactLeadLinkMock.mockReset();
    getCrmCompanyMock.mockReset();
    listCrmContactsMock.mockResolvedValue(page([]));
    updateCrmContactLeadLinkMock.mockResolvedValue({
      contact_id: "contact-1",
      lead_id: "lead-1",
      linked: true,
      revision: 4,
    });
    getCrmCompanyMock.mockResolvedValue({
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
    });
  });

  it("shows an empty state and preserves the existing Lead profile", async () => {
    renderProfile();

    expect(
      await screen.findByText("No CRM Contacts are linked to this Lead yet."),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Ada Prospect" })).toBeVisible();
    expect(
      screen.getByRole("link", { name: "ada@example.com" }),
    ).toHaveAttribute("href", "mailto:ada@example.com");
    expect(screen.getByText("Legacy Company")).toBeVisible();
    expect(screen.getByText("We need a product demo.")).toBeVisible();
    expect(screen.getByRole("link", { name: "Open in Inbox" })).toHaveAttribute(
      "href",
      "/inbox?lead=lead-1",
    );
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        leadId: "lead-1",
        includeArchived: true,
        limit: 20,
        offset: 0,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("renders a single linked Contact and its CRM Company name", async () => {
    const linked = contact({ company_id: "company-1" });
    listCrmContactsMock.mockResolvedValue(page([linked]));

    renderProfile();

    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    expect(await screen.findByText("Company: Acme CRM")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledWith(
      "company-1",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("renders multiple linked Contacts", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([
        contact(),
        contact({
          id: "contact-2",
          display_name: "Katherine Johnson",
          email: "katherine@example.com",
        }),
      ]),
    );

    renderProfile();

    expect(await screen.findByText("Grace Hopper")).toBeVisible();
    expect(screen.getByText("Katherine Johnson")).toBeVisible();
    expect(screen.getByText("Linked Contacts (2)")).toBeVisible();
  });

  it("does not offer a Contact linked beyond the visible linked page", async () => {
    const user = userEvent.setup();
    const linkedOnAnotherPage = contact({ id: "contact-21" });
    const visibleLinkedContact = contact({
      id: "contact-1",
      display_name: "Katherine Johnson",
    });
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) => {
        if (params.leadId && params.q) {
          return page([linkedOnAnotherPage]);
        }
        if (params.leadId) {
          return {
            ...page([visibleLinkedContact]),
            total: 21,
          };
        }
        return page([linkedOnAnotherPage]);
      },
    );

    renderProfile();
    await user.type(
      screen.getByRole("searchbox", { name: "Search CRM Contacts" }),
      "Grace",
    );

    expect(
      await screen.findByText("No unlinked Contacts on this search page."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Link Grace Hopper" }),
    ).not.toBeInTheDocument();
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        q: "Grace",
        leadId: "lead-1",
        limit: 100,
        offset: 0,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("does not reuse linked-search results when the Lead changes", async () => {
    const user = userEvent.setup();
    const linkedToLeadTwo = contact({ id: "contact-lead-2" });
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) => {
        if (params.leadId && params.q) {
          return params.leadId === "lead-1"
            ? page([])
            : page([linkedToLeadTwo]);
        }
        if (params.leadId) {
          return page([]);
        }
        return page([linkedToLeadTwo]);
      },
    );

    const { rerender } = render(<CrmContactAssociations leadId="lead-1" />);
    await user.type(
      screen.getByRole("searchbox", { name: "Search CRM Contacts" }),
      "Grace",
    );
    expect(
      await screen.findByRole("button", { name: "Link Grace Hopper" }),
    ).toBeVisible();
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      expect.objectContaining({ q: "Grace", leadId: "lead-1" }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    rerender(<CrmContactAssociations leadId="lead-2" />);

    expect(
      await screen.findByText("No unlinked Contacts on this search page."),
    ).toBeVisible();
    expect(listCrmContactsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        q: "Grace",
        leadId: "lead-2",
        limit: 100,
        offset: 0,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(
      screen.queryByRole("button", { name: "Link Grace Hopper" }),
    ).not.toBeInTheDocument();
  });

  it("searches and links an existing Contact using its current revision", async () => {
    const user = userEvent.setup();
    const candidate = contact();
    let linked: CrmContact[] = [];
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) => {
        if (params.leadId) {
          return page(linked);
        }
        return page([candidate]);
      },
    );
    updateCrmContactLeadLinkMock.mockImplementation(
      async (contactId, request) => {
        linked = request.linked ? [candidate] : [];
        return {
          contact_id: contactId,
          lead_id: request.lead_id,
          linked: request.linked,
          revision: candidate.revision + 1,
        };
      },
    );

    renderProfile();

    await user.type(
      screen.getByRole("searchbox", { name: "Search CRM Contacts" }),
      "Grace",
    );
    await user.click(
      await screen.findByRole("button", { name: "Link Grace Hopper" }),
    );

    expect(updateCrmContactLeadLinkMock).toHaveBeenCalledWith("contact-1", {
      expected_revision: 3,
      lead_id: "lead-1",
      linked: true,
    });
    expect(
      await screen.findByText("Grace Hopper linked to this Lead."),
    ).toBeVisible();
    await waitFor(() =>
      expect(
        listCrmContactsMock.mock.calls.filter(
          ([params]) => params?.leadId && !params.q,
        ),
      ).toHaveLength(2),
    );
    expect(
      screen.queryByRole("button", { name: "Link Grace Hopper" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Unlink Grace Hopper" }),
    ).toBeVisible();
  });

  it("unlinks a Contact and refreshes the association list", async () => {
    const user = userEvent.setup();
    const linkedContact = contact();
    let linked = [linkedContact];
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        params.leadId ? page(linked) : page([]),
    );
    updateCrmContactLeadLinkMock.mockImplementation(
      async (contactId, request) => {
        linked = request.linked ? [linkedContact] : [];
        return {
          contact_id: contactId,
          lead_id: request.lead_id,
          linked: request.linked,
          revision: linkedContact.revision + 1,
        };
      },
    );

    renderProfile();
    await user.click(
      await screen.findByRole("button", { name: "Unlink Grace Hopper" }),
    );

    expect(updateCrmContactLeadLinkMock).toHaveBeenCalledWith("contact-1", {
      expected_revision: 3,
      lead_id: "lead-1",
      linked: false,
    });
    expect(
      await screen.findByText("No CRM Contacts are linked to this Lead yet."),
    ).toBeVisible();
  });

  it("does not offer linking a Contact that is already linked", async () => {
    const user = userEvent.setup();
    const linkedContact = contact();
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        page(params.leadId ? [linkedContact] : [linkedContact]),
    );

    renderProfile();
    await user.type(
      screen.getByRole("searchbox", { name: "Search CRM Contacts" }),
      "Grace",
    );

    expect(
      await screen.findByText("No unlinked Contacts on this search page."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Link Grace Hopper" }),
    ).not.toBeInTheDocument();
    expect(updateCrmContactLeadLinkMock).not.toHaveBeenCalled();
  });

  it("refreshes and explains a revision conflict", async () => {
    const user = userEvent.setup();
    let linkedContact = contact();
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        page(params.leadId ? [linkedContact] : []),
    );
    updateCrmContactLeadLinkMock.mockImplementationOnce(async () => {
      linkedContact = contact({ revision: 4 });
      throw new ApiError("Request failed: 409", 409, {
        detail: "Contact revision conflict",
      });
    });

    renderProfile();
    await user.click(
      await screen.findByRole("button", { name: "Unlink Grace Hopper" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This Contact changed after it was loaded.",
    );
    await waitFor(() =>
      expect(
        listCrmContactsMock.mock.calls.filter(([params]) => params?.leadId),
      ).toHaveLength(2),
    );
    await user.click(
      await screen.findByRole("button", { name: "Unlink Grace Hopper" }),
    );
    expect(updateCrmContactLeadLinkMock).toHaveBeenNthCalledWith(
      1,
      "contact-1",
      {
        expected_revision: 3,
        lead_id: "lead-1",
        linked: false,
      },
    );
    expect(updateCrmContactLeadLinkMock).toHaveBeenNthCalledWith(
      2,
      "contact-1",
      {
        expected_revision: 4,
        lead_id: "lead-1",
        linked: false,
      },
    );
  });

  it("reuses CRM Company names when paging linked Contacts", async () => {
    const user = userEvent.setup();
    const contacts = Array.from({ length: 21 }, (_, index) =>
      contact({
        id: `contact-${index + 1}`,
        display_name: `Contact ${index + 1}`,
        company_id: "company-1",
      }),
    );
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        params.leadId
          ? {
              items: contacts.slice(
                params.offset ?? 0,
                (params.offset ?? 0) + (params.limit ?? 20),
              ),
              limit: params.limit ?? 20,
              offset: params.offset ?? 0,
              total: contacts.length,
            }
          : page([]),
    );

    renderProfile();
    expect(await screen.findAllByText("Company: Acme CRM")).toHaveLength(20);
    await user.click(
      screen.getByRole("button", { name: "Next linked Contacts" }),
    );
    expect(await screen.findByText("Contact 21")).toBeVisible();
    expect(getCrmCompanyMock).toHaveBeenCalledTimes(1);
  });

  it("explains permission failures when linking a Contact", async () => {
    const user = userEvent.setup();
    listCrmContactsMock.mockImplementation(
      async (params: CrmContactListParams = {}) =>
        params.leadId ? page([]) : page([contact()]),
    );
    updateCrmContactLeadLinkMock.mockRejectedValue(
      new ApiError("Request failed: 403", 403, { detail: "forbidden" }),
    );

    renderProfile();
    await user.type(
      screen.getByRole("searchbox", { name: "Search CRM Contacts" }),
      "Grace",
    );
    await user.click(
      await screen.findByRole("button", { name: "Link Grace Hopper" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "You do not have permission to change this Contact's Lead associations.",
    );
  });

  it("prevents unlinking archived Contacts and surfaces failed loads", async () => {
    listCrmContactsMock.mockResolvedValue(
      page([contact({ archived_at: "2026-09-12T10:00:00Z" })]),
    );

    renderProfile();

    expect(
      await screen.findByText(
        "Archived — restore this Contact before changing its links.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Unlink Grace Hopper" }),
    ).toBeDisabled();

    listCrmContactsMock.mockRejectedValueOnce(
      new ApiError("Request failed: 500", 500, { detail: "unavailable" }),
    );
    render(<Customer360Profile lead={{ ...lead, id: "lead-2" }} />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Contacts could not be loaded.",
    );
  });
});
