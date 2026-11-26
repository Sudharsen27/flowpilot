import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getCrmContact,
  listCrmContacts,
  updateCrmContactLeadLink,
} from "@/lib/api/crm-contacts";

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
      leadId: "lead/1",
      includeArchived: true,
      limit: 101,
      offset: -3,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/contacts?q=Ada+%2F+Co&lead_id=lead%2F1&include_archived=true&limit=100&offset=0",
      expect.objectContaining({ method: "GET" }),
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
});
