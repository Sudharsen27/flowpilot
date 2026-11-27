import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  archiveCrmCompany,
  createCrmCompany,
  getCrmCompany,
  listCrmCompanies,
  restoreCrmCompany,
  updateCrmCompany,
  type CrmCompanyDetail,
} from "@/lib/api/crm-companies";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("CRM Company API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("gets company details from the CRM endpoint with an encoded ID", async () => {
    const company: CrmCompanyDetail = {
      id: "company/1",
      name: "Acme",
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
      owner_user_id: "user-1",
      revision: 1,
      archived_at: null,
      created_at: "2026-09-01T10:00:00Z",
      updated_at: "2026-09-01T10:00:00Z",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(company), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const controller = new AbortController();

    await getCrmCompany("company/1", { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies/company%2F1",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });

  it("lists Companies with encoded filters, bounded pagination, and an abort signal", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({ items: [], limit: 100, offset: 0, total: 0 }),
      );
    const controller = new AbortController();

    await listCrmCompanies(
      {
        q: "Acme / Co ",
        lifecycleStatus: "CUSTOMER",
        ownerUserId: "user/1",
        includeArchived: true,
        limit: 101,
        offset: -3,
      },
      { signal: controller.signal },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies?q=Acme+%2F+Co&lifecycle_status=CUSTOMER&owner_user_id=user%2F1&include_archived=true&limit=100&offset=0",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });

  it("creates a Company with the backend request fields", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "company-1" }, 201));
    const input = {
      name: "Acme",
      website_domain: "acme.example",
      lifecycle_status: "CUSTOMER" as const,
      owner_user_id: "user-1",
    };

    await createCrmCompany(input);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(input),
      }),
    );
  });

  it("updates a Company with an encoded ID and expected revision", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "company/1", revision: 2 }));
    const input = { expected_revision: 1, name: "Acme Group" };

    await updateCrmCompany("company/1", input);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies/company%2F1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify(input),
      }),
    );
  });

  it.each([
    ["archives", archiveCrmCompany, "archive"],
    ["restores", restoreCrmCompany, "restore"],
  ] as const)(
    "%s a Company using the expected revision",
    async (_description, mutate, action) => {
      const fetchMock = vi
        .spyOn(globalThis, "fetch")
        .mockResolvedValue(jsonResponse({ id: "company/1", revision: 2 }));

      await mutate("company/1", 1);

      expect(fetchMock).toHaveBeenCalledWith(
        `http://localhost:8000/api/v1/companies/company%2F1/${action}`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ expected_revision: 1 }),
        }),
      );
    },
  );

  it("propagates API errors from Company requests", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ detail: "Forbidden" }, 403),
    );

    await expect(listCrmCompanies()).rejects.toMatchObject({
      name: "ApiError",
      status: 403,
      body: { detail: "Forbidden" },
    });
  });
});
