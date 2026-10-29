import { describe, expect, it } from "vitest";

import { buildLeadHref, parseLeadSalesRunSearchParams } from "@/lib/lead-url";

function parse(query: string) {
  return parseLeadSalesRunSearchParams(new URLSearchParams(query));
}

describe("lead URL", () => {
  it("builds lead hrefs with an optional Sales Run selection", () => {
    expect(buildLeadHref("lead-1")).toBe("/leads/lead-1");
    expect(buildLeadHref("lead/1")).toBe("/leads/lead%2F1");
    expect(buildLeadHref("lead-1", { salesRunId: "run-1", agentId: "agent-1" })).toBe(
      "/leads/lead-1?sales_run=run-1&agent=agent-1",
    );
    expect(buildLeadHref("lead-1", { salesRunId: "run-1" })).toBe("/leads/lead-1");
    expect(buildLeadHref("  ")).toBeNull();
    expect(buildLeadHref("l".repeat(37))).toBeNull();
  });

  it("parses a complete Sales Run selection only", () => {
    expect(parse("sales_run=run-1&agent=agent-1")).toEqual({
      salesRunId: "run-1",
      agentId: "agent-1",
    });
    expect(parse("sales_run=run-1")).toBeNull();
    expect(parse("agent=agent-1")).toBeNull();
    expect(parse(`sales_run=${"r".repeat(37)}&agent=agent-1`)).toBeNull();
    expect(parse("")).toBeNull();
  });
});
