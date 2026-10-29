import { describe, expect, it } from "vitest";

import {
  AGENT_EXECUTIONS_PAGE_SIZE,
  agentExecutionsUrlEquals,
  buildAgentExecutionsHref,
  parseAgentExecutionsSearchParams,
  serializeAgentExecutionsSearchParams,
  type AgentExecutionsUrlState,
} from "@/lib/agent-executions-url";

const defaults: AgentExecutionsUrlState = {
  status: null,
  agentId: null,
  leadId: null,
  limit: AGENT_EXECUTIONS_PAGE_SIZE,
  offset: 0,
};

function parse(query: string) {
  return parseAgentExecutionsSearchParams(new URLSearchParams(query));
}

describe("agent executions URL state", () => {
  it("defaults to all statuses, no filters, first page", () => {
    expect(parse("")).toEqual(defaults);
  });

  it("parses every supported parameter", () => {
    expect(
      parse("status=FAILED&agent_id=agent-1&lead_id=lead-1&limit=50&offset=40"),
    ).toEqual({
      status: "FAILED",
      agentId: "agent-1",
      leadId: "lead-1",
      limit: 50,
      offset: 40,
    });
  });

  it("accepts lower-case status and rejects unknown statuses", () => {
    expect(parse("status=running").status).toBe("RUNNING");
    expect(parse("status=STALE").status).toBeNull();
    expect(parse("status=").status).toBeNull();
  });

  it("drops blank and oversized IDs instead of sending them", () => {
    expect(parse("agent_id=%20%20").agentId).toBeNull();
    expect(parse(`agent_id=${"a".repeat(37)}`).agentId).toBeNull();
    expect(parse(`lead_id=${"b".repeat(37)}`).leadId).toBeNull();
    expect(parse(`lead_id=${"b".repeat(36)}`).leadId).toBe("b".repeat(36));
    expect(parse("agent_id=%20agent-1%20").agentId).toBe("agent-1");
  });

  it("clamps limit and rejects invalid offsets", () => {
    expect(parse("limit=500").limit).toBe(50);
    expect(parse("limit=0").limit).toBe(AGENT_EXECUTIONS_PAGE_SIZE);
    expect(parse("limit=abc").limit).toBe(AGENT_EXECUTIONS_PAGE_SIZE);
    expect(parse("offset=-20").offset).toBe(0);
    expect(parse("offset=2.5").offset).toBe(0);
    expect(parse("offset=abc").offset).toBe(0);
    expect(parse("offset=99999999999999999999").offset).toBe(0);
  });

  it("serializes only non-default values", () => {
    expect(serializeAgentExecutionsSearchParams(defaults)).toBe("");
    expect(
      serializeAgentExecutionsSearchParams({
        status: "RUNNING",
        agentId: "agent/1",
        leadId: "lead-1",
        limit: 50,
        offset: 20,
      }),
    ).toBe("status=RUNNING&agent_id=agent%2F1&lead_id=lead-1&limit=50&offset=20");
  });

  it("round-trips through parse and serialize", () => {
    const state: AgentExecutionsUrlState = {
      status: "COMPLETED",
      agentId: "agent-1",
      leadId: null,
      limit: AGENT_EXECUTIONS_PAGE_SIZE,
      offset: 40,
    };
    expect(parse(serializeAgentExecutionsSearchParams(state))).toEqual(state);
  });

  it("compares states field by field", () => {
    expect(agentExecutionsUrlEquals(defaults, { ...defaults })).toBe(true);
    expect(agentExecutionsUrlEquals(defaults, { ...defaults, offset: 20 })).toBe(
      false,
    );
    expect(
      agentExecutionsUrlEquals(defaults, { ...defaults, leadId: "lead-1" }),
    ).toBe(false);
  });

  it("builds deep links for agents, leads and statuses", () => {
    expect(buildAgentExecutionsHref()).toBe("/agents/executions");
    expect(buildAgentExecutionsHref({ agentId: "agent-1" })).toBe(
      "/agents/executions?agent_id=agent-1",
    );
    expect(buildAgentExecutionsHref({ leadId: "lead-1" })).toBe(
      "/agents/executions?lead_id=lead-1",
    );
    expect(buildAgentExecutionsHref({ status: "FAILED" })).toBe(
      "/agents/executions?status=FAILED",
    );
    expect(buildAgentExecutionsHref({ agentId: "x".repeat(40) })).toBe(
      "/agents/executions",
    );
  });
});
