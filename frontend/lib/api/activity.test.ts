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
    const controller = new AbortController();

    await listActivity(
      {
        type: "AI_ACTION",
        entity_type: "CONTACT",
        entity_id: "contact/1",
        q: "qualified / lead",
        limit: 20,
        offset: 20,
      },
      { signal: controller.signal },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/activity?type=AI_ACTION&entity_type=CONTACT&entity_id=contact%2F1&q=qualified+%2F+lead&limit=20&offset=20",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
        signal: controller.signal,
        headers: expect.not.objectContaining({
          Authorization: expect.anything(),
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
    const controller = new AbortController();

    await getActivity("event/1", { signal: controller.signal });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/activity/event%2F1",
      expect.objectContaining({
        method: "GET",
        signal: controller.signal,
      }),
    );
  });
});
