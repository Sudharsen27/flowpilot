import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getPublicEnquiryForm,
  submitPublicEnquiry,
  getWebsiteCaptureSettings,
  updateWebsiteCaptureSettings,
} from "@/lib/api/website-capture";

describe("Website capture API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
  });

  it("loads the public form without an authorization header", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ organization_name: "Acme" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getPublicEnquiryForm("acme/co");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/public/organizations/acme%2Fco/enquiries",
      expect.objectContaining({
        method: "GET",
        headers: expect.not.objectContaining({
          Authorization: expect.anything(),
        }),
      }),
    );
  });

  it("posts a public enquiry without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    await submitPublicEnquiry("acme", {
      name: "Ada",
      email: "ada@example.com",
      enquiry: "Need a demo",
      website: null,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/public/organizations/acme/enquiries",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Ada",
          email: "ada@example.com",
          enquiry: "Need a demo",
          website: null,
        }),
      }),
    );
  });

  it("patches authenticated capture settings", async () => {
    const payload = {
      website_capture_enabled: true,
      sales_agent_auto_start_enabled: true,
      default_sales_agent_id: "agent-sales-1",
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await getWebsiteCaptureSettings();
    await updateWebsiteCaptureSettings(payload);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/organizations/current/website-capture",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer stored-token",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/organizations/current/website-capture",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).not.toHaveProperty(
      "organization_id",
    );
  });
});
