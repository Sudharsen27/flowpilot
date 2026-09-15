import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/client";
import {
  cancelSalesRun,
  getSalesRun,
  listLeadSalesRuns,
  listOrganizationSalesRuns,
  listSalesRuns,
  sendSalesRun,
  scheduleSalesRunFollowUp,
  startSalesRun,
  startLeadSalesRun,
} from "@/lib/api/sales-runs";

const failedRun = {
  id: "run-fail-1",
  agent_id: "agent-1",
  lead_id: "lead-1",
  status: "FAILED",
  stage: "QUALIFY",
  qualification_id: "q-1",
  response_draft_id: null,
  email_send_id: null,
  follow_up_id: null,
  failure_category: "PROVIDER_ERROR",
  error: "AI provider request failed",
  initiated_by_user_id: "user-1",
  revision: 2,
  started_at: "2026-09-11T10:00:00Z",
  completed_at: "2026-09-11T10:00:02Z",
  created_at: "2026-09-11T10:00:00Z",
  updated_at: "2026-09-11T10:00:02Z",
};

describe("Sales run API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.setItem("flowpilot.access_token", "agent-token");
  });

  it("starts a sales run on the encoded agent path without organization_id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(failedRun), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await startSalesRun("agent/1", {
      enquiry: "Need a demo",
      name: "Ada",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enquiry: "Need a demo", name: "Ada" }),
      }),
    );
    expect(String(fetchMock.mock.calls[0]?.[1]?.body)).not.toContain(
      "organization_id",
    );
  });

  it("lists sales runs with optional status and pagination only when provided", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ items: [], limit: 20, offset: 0, total: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await listSalesRuns("agent/1");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs",
      expect.any(Object),
    );
    await listSalesRuns("agent/1", {
      status: "WAITING_APPROVAL",
      limit: 20,
      offset: 0,
    });
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs?status=WAITING_APPROVAL&limit=20&offset=0",
      expect.any(Object),
    );
    await listOrganizationSalesRuns({
      status: "FAILED",
      stage: "SEND",
      limit: 20,
      offset: 0,
    });
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8000/api/v1/sales-runs?status=FAILED&stage=SEND&limit=20&offset=0",
      expect.any(Object),
    );
  });

  it("gets, cancels, and lists nested and organization sales runs with encoded ids", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(failedRun), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await getSalesRun("agent/1", "run/1");
    await cancelSalesRun("agent/1", "run/1", { expected_revision: 1 });
    await sendSalesRun("agent/1", "run/1", { expected_revision: 2 });
    await scheduleSalesRunFollowUp("agent/1", "run/1", {
      expected_revision: 3,
      due_at: "2030-06-15T10:30:00.000Z",
      type: "EMAIL_FOLLOW_UP",
      body_text: "Checking in.",
    });
    const body = String(fetchMock.mock.calls.at(-1)?.[1]?.body);
    expect(body).toContain("Checking in.");
    expect(body).not.toContain("organization_id");
    expect(body).not.toContain("email_send_id");
    expect(body).not.toContain("draft_id");
    await listLeadSalesRuns("lead/1");
    await listOrganizationSalesRuns({ status: "WAITING_APPROVAL" });
    const urls = fetchMock.mock.calls.map((call) => call[0]);
    expect(urls).toContain(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs/run%2F1",
    );
    expect(urls).toContain(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs/run%2F1/cancel",
    );
    expect(urls).toContain(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs/run%2F1/send",
    );
    expect(urls).toContain(
      "http://localhost:8000/api/v1/agents/agent%2F1/sales-runs/run%2F1/schedule-follow-up",
    );
    expect(urls).toContain(
      "http://localhost:8000/api/v1/leads/lead%2F1/sales-runs",
    );
    expect(urls).toContain(
      "http://localhost:8000/api/v1/sales-runs?status=WAITING_APPROVAL",
    );
  });

  it("starts a sales run from a lead path without lead_id in the body", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(failedRun), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await startLeadSalesRun("lead/1", {
      enquiry: "Need a demo",
      agent_id: "agent/1",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/leads/lead%2F1/sales-runs",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ enquiry: "Need a demo", agent_id: "agent/1" }),
      }),
    );
    const body = String(fetchMock.mock.calls[0]?.[1]?.body);
    expect(body).not.toContain("lead_id");
    expect(body).not.toContain("organization_id");
  });

  it("recovers a failed sales run from a 502 body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ ...failedRun, detail: "AI provider request failed" }),
        { status: 502, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await startSalesRun("agent-1", { enquiry: "Need a demo", name: "Ada" });
    expect(result.status).toBe("FAILED");
    expect(result.id).toBe("run-fail-1");
  });

  it("recovers a failed sales run from a 502 send body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          ...failedRun,
          status: "FAILED",
          stage: "SEND",
          detail: "Email provider request failed",
        }),
        { status: 502, headers: { "Content-Type": "application/json" } },
      ),
    );
    const result = await sendSalesRun("agent-1", "run-fail-1", {
      expected_revision: 2,
    });
    expect(result.status).toBe("FAILED");
    expect(result.stage).toBe("SEND");
  });

  it("throws when a 502 body is not a failed sales run", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "upstream" }), {
        status: 502,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      startSalesRun("agent-1", { enquiry: "Need a demo", name: "Ada" }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
