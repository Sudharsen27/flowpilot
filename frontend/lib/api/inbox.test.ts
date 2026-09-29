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
          human_attention_count: 0,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await getInbox({
      q: "ada / lead",
      conversation_state: "NEEDS_APPROVAL",
      source: "WEBSITE",
      needs_approval: true,
      human_attention_required: true,
      limit: 20,
      offset: 20,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/inbox?q=ada+%2F+lead&human_attention_required=true&needs_approval=true&conversation_state=NEEDS_APPROVAL&source=WEBSITE&limit=20&offset=20",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer inbox-token",
        }),
      }),
    );
  });

  it("gets conversation detail and merges the real escalation Activity once", async () => {
    const inboxResponse = new Response(
      JSON.stringify({
        lead: { lead_id: "lead/1", human_attention_required: true },
        items: [],
        total_items: 0,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    const activityEvent = {
      id: "activity-1",
      type: "AI_ACTION",
      title: "Human attention required",
      summary: null,
      occurred_at: "2026-09-29T10:00:00Z",
      actor_type: "AGENT",
      actor_user_id: null,
      agent_id: null,
      entity_type: "LEAD",
      entity_id: "lead/1",
      lead_id: "lead/1",
      status: "REQUIRED",
      sales_run_id: null,
      execution_id: null,
      email_send_id: null,
      follow_up_id: null,
      follow_up_execution_id: null,
      draft_id: null,
      qualification_id: null,
    };
    const activityResponse = new Response(
      JSON.stringify({
        items: [activityEvent],
        limit: 50,
        offset: 0,
        total: 1,
        type_counts: { AI_ACTION: 1, APPROVAL: 0, HUMAN_ACTION: 0, SYSTEM_EVENT: 0 },
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(inboxResponse)
      .mockResolvedValueOnce(activityResponse);
    const result = await getInboxConversation("lead/1");

    expect(result.items).toHaveLength(1);
    expect(result.items[0]).toMatchObject({
      kind: "HUMAN_ATTENTION_REQUIRED",
      title: "Human attention required",
      activity_id: "activity-1",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/inbox/lead%2F1",
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/activity?type=AI_ACTION&entity_type=LEAD&lead_id=lead%2F1&q=Human+attention+required&limit=50",
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
          human_attention_count: 0,
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
