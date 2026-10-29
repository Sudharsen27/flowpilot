import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import { getPipelineForecast } from "@/lib/api/pipeline";

function mockFetch(body: unknown = {}, status = 200) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

describe("pipeline forecast API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "forecast-token");
  });

  it("requests the forecast with backend parameter names and the session token", async () => {
    const fetchMock = mockFetch({ currency: "INR", total: "10.50" });
    const result = await getPipelineForecast({ granularity: "month", periods: 12 });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toMatch(/\/api\/v1\/pipeline\/forecast\?granularity=month&periods=12$/);
    expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer forecast-token");
    // Decimal strings are passed through untouched.
    expect(result).toEqual({ currency: "INR", total: "10.50" });
  });

  it("passes the abort signal to fetch so cancelled queries stop the request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("The operation was aborted.", "AbortError")),
          );
        }),
    );
    const controller = new AbortController();
    const pending = getPipelineForecast({ granularity: "quarter", periods: 4 }, { signal: controller.signal });
    expect(fetchMock.mock.calls[0]?.[1]?.signal).toBe(controller.signal);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });

  it("surfaces backend validation errors", async () => {
    mockFetch({ detail: "periods must be between 1 and 8 for quarter" }, 422);
    await expect(getPipelineForecast({ granularity: "quarter", periods: 9 })).rejects.toMatchObject({
      status: 422,
    } satisfies Partial<ApiError>);
  });
});
