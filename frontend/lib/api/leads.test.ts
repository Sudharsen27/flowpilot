import { beforeEach, describe, expect, it, vi } from "vitest";

import { createLead, generateLeadResponseDraft, getLead, getLeads, qualifyLead, updateLead } from "@/lib/api/leads";

describe("Lead API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "lead-token");
  });

  it("lists leads with encoded query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          limit: 20,
          offset: 0,
          total: 0,
          status_counts: {},
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getLeads({
      status: "NEW",
      source: "WEBSITE",
      q: "Ada / Co",
      limit: 20,
      offset: 20,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads?status=NEW&source=WEBSITE&q=Ada+%2F+Co&limit=20&offset=20",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer lead-token",
        }),
      }),
    );
  });

  it("gets an encoded lead detail endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "lead/1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getLead("lead/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("posts a create payload without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "new-lead" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await createLead({
      name: "Ada Prospect",
      email: "ada@example.com",
      source: "MANUAL",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          name: "Ada Prospect",
          email: "ada@example.com",
          source: "MANUAL",
        }),
      }),
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).not.toHaveProperty("organization_id");
  });

  it("patches an encoded lead id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "lead/1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await updateLead("lead/1", { status: "CONTACTED" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ status: "CONTACTED" }),
      }),
    );
  });

  it("preserves global 401 session invalidation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getLeads()).rejects.toMatchObject({ status: 401 });
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
  });

  it("posts qualification to an encoded lead id without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "q-1", status: "COMPLETED" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await qualifyLead("lead/1", { enquiry: "We want a demo" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1/qualify",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enquiry: "We want a demo" }),
      }),
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).not.toHaveProperty("organization_id");
  });

  it("posts a response draft to an encoded lead id without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "d-1", status: "COMPLETED" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await generateLeadResponseDraft("lead/1", { enquiry: "We want a demo" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1/respond",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enquiry: "We want a demo" }),
      }),
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).not.toHaveProperty("organization_id");
  });
});
