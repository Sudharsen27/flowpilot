import { beforeEach, describe, expect, it, vi } from "vitest";

import { getCrmCompany, type CrmCompanyDetail } from "@/lib/api/crm-companies";

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
});
