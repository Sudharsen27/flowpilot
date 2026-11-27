import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  archiveCrmContact,
  createCrmContact,
  getCrmContact,
  listCrmContactLeads,
  listCrmContacts,
  restoreCrmContact,
  updateCrmContact,
  updateCrmContactLeadLink,
} from "@/lib/api/crm-contacts";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("CRM Contact API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("gets Contact details from the CRM endpoint with an encoded ID", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "contact/1",
          display_name: "Grace Hopper",
          first_name: "Grace",
          last_name: "Hopper",
          job_title: "Engineer",
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
          updated_at: "2026-09-01T10:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const controller = new AbortController();

    await getCrmContact("contact/1", { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts/contact%2F1",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });

  it("lists Contacts with encoded CRM filters and bounded pagination", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        new Response(
          JSON.stringify({ items: [], limit: 100, offset: 0, total: 0 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );

    await listCrmContacts({
      q: "Ada / Co",
      companyId: "company/1",
      status: "ACTIVE",
      ownerUserId: "user/1",
      leadId: "lead/1",
      includeArchived: true,
      limit: 101,
      offset: -3,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts?q=Ada+%2F+Co&company_id=company%2F1&status=ACTIVE&owner_user_id=user%2F1&lead_id=lead%2F1&include_archived=true&limit=100&offset=0",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("forwards an abort signal when listing Contacts", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({ items: [], limit: 20, offset: 0, total: 0 }),
      );
    const controller = new AbortController();

    await listCrmContacts({}, { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });

  it("creates a Contact with the backend request fields", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "contact-1" }, 201));
    const input = {
      display_name: "Grace Hopper",
      email: "grace@example.com",
      company_id: "company-1",
      status: "ACTIVE" as const,
      owner_user_id: "user-1",
    };

    await createCrmContact(input);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(input),
      }),
    );
  });

  it("updates a Contact with an encoded ID and expected revision", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "contact/1", revision: 2 }));
    const input = { expected_revision: 1, display_name: "Grace Hopper" };

    await updateCrmContact("contact/1", input);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts/contact%2F1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    );
  });

  it.each([
    ["archives", archiveCrmContact, "archive"],
    ["restores", restoreCrmContact, "restore"],
  ] as const)(
    "%s a Contact using the expected revision",
    async (_description, mutate, action) => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(jsonResponse({ id: "contact/1", revision: 2 }));

      await mutate("contact/1", 1);

      expect(fetchMock).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/contacts/contact%2F1/${action}`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ expected_revision: 1 }),
        }),
      );
    },
  );

  it("lists a Contact's Leads with encoded ID, pagination, and an abort signal", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({ items: [], limit: 100, offset: 5, total: 0 }),
      );
    const controller = new AbortController();

    await listCrmContactLeads(
      "contact/1",
      { limit: 101, offset: 5 },
      { signal: controller.signal },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts/contact%2F1/leads?limit=100&offset=5",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });

  it("sends the expected revision when changing a Contact-Lead association", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          contact_id: "contact/1",
          lead_id: "lead-1",
          linked: true,
          revision: 4,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await updateCrmContactLeadLink("contact/1", {
      expected_revision: 3,
      lead_id: "lead-1",
      linked: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts/contact%2F1/leads",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          expected_revision: 3,
          lead_id: "lead-1",
          linked: true,
        }),
      }),
    );
  });

  it("propagates API errors from Contact requests", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Contact not found" }, 404),
    );

    await expect(listCrmContactLeads("missing-contact")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      body: { detail: "Contact not found" },
    });
  });
});
