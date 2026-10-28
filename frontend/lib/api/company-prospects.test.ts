import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import { getCompanyProspectDuplicateAssessment } from "@/lib/api/company-prospects";

describe("Company prospects API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "prospects-token");
  });

  it("requests the single prospect duplicate assessment with an encoded id", async () => {
    const body = {
      assessments: [],
      total_evaluated: 1,
      persisted_cin_available: false,
    };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      getCompanyProspectDuplicateAssessment("company 1/x"),
    ).resolves.toEqual(body);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/company-prospects/company%201%2Fx/duplicate-assessment",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer prospects-token",
        }),
      }),
    );
  });

  it("surfaces API errors with their status", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Company prospect not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const failure = await getCompanyProspectDuplicateAssessment("missing").catch(
      (cause: unknown) => cause,
    );
    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(404);
  });
});
