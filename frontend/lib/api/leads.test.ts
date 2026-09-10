import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  approveLeadResponseDraft,
  createLead,
  generateLeadResponseDraft,
  getLead,
  getLeads,
  getLeadResponseDraft,
  qualifyLead,
  rejectLeadResponseDraft,
  sendLeadResponseDraft,
  updateLead,
  updateLeadResponseDraft,
  cancelLeadFollowUp,
  completeLeadFollowUp,
  createLeadFollowUp,
  getLeadFollowUp,
  getLeadFollowUps,
  updateLeadFollowUp,
} from "@/lib/api/leads";

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

  it("gets, patches, approves, and rejects encoded draft ids without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ id: "d/1", status: "COMPLETED" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await getLeadResponseDraft("lead/1", "d/1");
    await updateLeadResponseDraft("lead/1", "d/1", {
      response: "Edited",
      expected_revision: 1,
    });
    await approveLeadResponseDraft("lead/1", "d/1", { expected_revision: 2 });
    await rejectLeadResponseDraft("lead/1", "d/1", {
      expected_revision: 3,
      reason: "Too generic",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "http://localhost:8000/api/v1/leads/lead%2F1/response-drafts/d%2F1",
    );
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          response: "Edited",
          expected_revision: 1,
        }),
      }),
    );
    expect(String(fetchMock.mock.calls[2]?.[0])).toContain(
      "/response-drafts/d%2F1/approve",
    );
    expect(String(fetchMock.mock.calls[3]?.[0])).toContain(
      "/response-drafts/d%2F1/reject",
    );
    for (const call of fetchMock.mock.calls) {
      const payload = call[1]?.body;
      if (typeof payload === "string") {
        expect(JSON.parse(payload)).not.toHaveProperty("organization_id");
      }
    }
  });

  it("posts send without recipient or sender overrides", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "s-1", status: "SENT" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await sendLeadResponseDraft("lead/1", "d/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1/response-drafts/d%2F1/send",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({}),
      }),
    );
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).not.toHaveProperty("to");
    expect(body).not.toHaveProperty("from");
    expect(body).not.toHaveProperty("organization_id");
  });

  it("encodes follow-up paths without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ items: [], limit: 20, offset: 0, total: 0, id: "fu/1" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await getLeadFollowUps("lead/1", { status: "PENDING", overdue: true, limit: 20, offset: 0 });
    await getLeadFollowUp("lead/1", "fu/1");
    await createLeadFollowUp("lead/1", {
      due_at: "2030-06-15T10:30:00.000Z",
      type: "EMAIL_FOLLOW_UP",
      notes: "Ping",
      body_text: "Checking in on your enquiry.",
    });
    await updateLeadFollowUp("lead/1", "fu/1", {
      expected_revision: 1,
      due_at: "2030-06-16T10:30:00.000Z",
    });
    await completeLeadFollowUp("lead/1", "fu/1", { expected_revision: 2 });
    await cancelLeadFollowUp("lead/1", "fu/1", { expected_revision: 3 });
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      "http://localhost:8000/api/v1/leads/lead%2F1/follow-ups?status=PENDING&overdue=true&limit=20&offset=0",
    );
    expect(String(fetchMock.mock.calls[1]?.[0])).toBe(
      "http://localhost:8000/api/v1/leads/lead%2F1/follow-ups/fu%2F1",
    );
    expect(String(fetchMock.mock.calls[5]?.[0])).toContain("/follow-ups/fu%2F1/cancel");
    for (const call of fetchMock.mock.calls) {
      const payload = call[1]?.body;
      if (typeof payload === "string") {
        expect(JSON.parse(payload)).not.toHaveProperty("organization_id");
      }
    }
  });
});
