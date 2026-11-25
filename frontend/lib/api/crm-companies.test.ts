import { beforeEach, describe, expect, it, vi } from "vitest";

import { getCrmCompany } from "@/lib/api/crm-companies";

describe("CRM Company API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("gets company details from the CRM endpoint with an encoded ID", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "company/1",
          name: "Acme",
          website_domain: "acme.example",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await getCrmCompany("company/1");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/companies/company%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
