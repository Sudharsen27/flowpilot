import { beforeEach, describe, expect, it, vi } from "vitest";

import { getActivity, listActivity } from "@/lib/api/activity";

describe("Activity API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "activity-token");
  });

  it("lists activity with encoded query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          limit: 20,
          offset: 0,
          total: 0,
          type_counts: {},
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    await listActivity({
      type: "AI_ACTION",
      entity_type: "LEAD",
      q: "qualified / lead",
      limit: 20,
      offset: 20,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/activity?type=AI_ACTION&entity_type=LEAD&q=qualified+%2F+lead&limit=20&offset=20",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer activity-token",
        }),
      }),
    );
  });

  it("gets encoded activity detail", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "event/1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getActivity("event/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/activity/event%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });
});
