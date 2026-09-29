import { beforeEach, describe, expect, it, vi } from "vitest";

import { getInbox, getInboxConversation } from "@/lib/api/inbox";

describe("Inbox API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "inbox-token");
  });

  it("lists inbox with encoded query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          limit: 20,
          offset: 0,
          total: 0,
          state_counts: { OPEN: 0, NEEDS_APPROVAL: 0, CLOSED: 0 },
          needs_approval_count: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getInbox({
      q: "ada / lead",
      conversation_state: "NEEDS_APPROVAL",
      source: "WEBSITE",
      needs_approval: true,
      limit: 20,
      offset: 20,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/inbox?q=ada+%2F+lead&needs_approval=true&conversation_state=NEEDS_APPROVAL&source=WEBSITE&limit=20&offset=20",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer inbox-token",
        }),
      }),
    );
  });

  it("gets encoded inbox conversation detail", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          lead: { lead_id: "lead/1" },
          items: [],
          total_items: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getInboxConversation("lead/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/inbox/lead%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("omits empty optional filters from the query string", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          limit: 20,
          offset: 0,
          total: 0,
          state_counts: { OPEN: 0, NEEDS_APPROVAL: 0, CLOSED: 0 },
          needs_approval_count: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getInbox({ q: "   ", limit: 20, offset: 0 });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/inbox?limit=20&offset=0",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
