import { describe, expect, it } from "vitest";

import {
  DEAL_STAGES,
  OPEN_DEAL_STAGES,
  canChangeStage,
  canCorrectWonAmount,
  creatableStages,
} from "@/lib/deals";
import type { DealStage } from "@/types/api";

const ROLES = ["OWNER", "ADMIN", "MEMBER", undefined] as const;

describe("deal permissions", () => {
  it("lets members create only open deals and managers create in every stage", () => {
    expect(OPEN_DEAL_STAGES).toEqual(["QUALIFICATION", "DISCOVERY", "PROPOSAL", "NEGOTIATION"]);
    expect(creatableStages("OWNER")).toEqual(DEAL_STAGES);
    expect(creatableStages("ADMIN")).toEqual(DEAL_STAGES);
    expect(creatableStages("MEMBER")).toEqual(OPEN_DEAL_STAGES);
    expect(creatableStages(undefined)).toEqual(OPEN_DEAL_STAGES);
  });

  it("limits leaving CLOSED_WON to managers and leaves other moves open", () => {
    for (const role of ROLES) {
      const manager = role === "OWNER" || role === "ADMIN";
      expect(canChangeStage({ stage: "CLOSED_WON" }, role)).toBe(manager);
      for (const stage of DEAL_STAGES.filter((value): value is DealStage => value !== "CLOSED_WON")) {
        expect(canChangeStage({ stage }, role)).toBe(true);
      }
    }
  });

  it("offers amount corrections to managers on won deals only", () => {
    expect(canCorrectWonAmount({ stage: "CLOSED_WON" }, "OWNER")).toBe(true);
    expect(canCorrectWonAmount({ stage: "CLOSED_WON" }, "ADMIN")).toBe(true);
    expect(canCorrectWonAmount({ stage: "CLOSED_WON" }, "MEMBER")).toBe(false);
    expect(canCorrectWonAmount({ stage: "CLOSED_LOST" }, "OWNER")).toBe(false);
    expect(canCorrectWonAmount({ stage: "PROPOSAL" }, "ADMIN")).toBe(false);
  });
});
