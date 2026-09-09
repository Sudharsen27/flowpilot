import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  createAgent,
  getAgent,
  getAgents,
  updateAgent,
} from "@/lib/api/agents";

describe("Agent API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "agent-token");
  });

  it("gets the authenticated agent list endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgents();
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents",
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
  });

  it("uses backend-supported status and agent_type query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgents({ status: "ACTIVE", agentType: "SALES" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents?status=ACTIVE&agent_type=SALES",
      expect.any(Object),
    );
  });

  it("gets an encoded agent detail endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "agent/1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await getAgent("agent/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("preserves global 401 session invalidation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid token" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(getAgents()).rejects.toMatchObject({ status: 401 });
    expect(window.localStorage.getItem("flowpilot.access_token")).toBeNull();
  });

  it("posts only the supported create payload", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "new-agent" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const payload = {
      name: "Support agent",
      description: "Handles support.",
      agent_type: "SUPPORT" as const,
      system_instructions: "Be concise.",
    };
    await createAgent(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(payload),
      }),
    );
  });

  it("patches changed configuration through the authenticated client", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ id: "agent-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await updateAgent("agent-1", { name: "Renamed" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent-1",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ name: "Renamed" }),
        headers: expect.objectContaining({
          Authorization: "Bearer agent-token",
        }),
      }),
    );
  });
});
