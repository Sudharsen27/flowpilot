import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiGet, apiPost } from "@/lib/api/client";

describe("API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("adds the stored bearer token and returns typed JSON", async () => {
    window.localStorage.setItem("flowpilot.access_token", "stored-token");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await apiGet<{ status: string }>("/health");

    expect(result.status).toBe("ok");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer stored-token",
        }),
      }),
    );
  });

  it("keeps JSON POST behavior working", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ access_token: "token" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await apiPost("/api/v1/auth/login", {
      email: "owner@example.com",
      password: "password12",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "owner@example.com",
          password: "password12",
        }),
      }),
    );
  });

  it("clears an invalid token on a 401 response", async () => {
    window.localStorage.setItem("flowpilot.access_token", "expired-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(apiGet("/api/v1/users/me")).rejects.toMatchObject({
      status: 401,
    });
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
  });

  it("attaches parsed JSON bodies to API errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token", extra: "keep" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(apiGet("/api/v1/users/me")).rejects.toMatchObject({
      status: 401,
      body: { detail: "Invalid token", extra: "keep" },
    });
  });
});
