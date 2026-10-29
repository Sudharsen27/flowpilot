import { describe, expect, it } from "vitest";

import {
  DEAL_STAGES,
  OPEN_DEAL_STAGES,
  canChangeStage,
  canCorrectWonAmount,
  FORECAST_CATEGORIES,
  creatableStages,
  forecastCategoryAfterMove,
  forecastCategoryLabel,
  isForecastCategory,
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

describe("forecast categories", () => {
  it("lists the stored categories from least to most confident", () => {
    expect(FORECAST_CATEGORIES).toEqual(["PIPELINE", "BEST_CASE", "COMMIT"]);
    expect(isForecastCategory("COMMIT")).toBe(true);
    // Closed is derived from the stage and is never a stored or filterable value.
    expect(isForecastCategory("CLOSED")).toBe(false);
    expect(isForecastCategory("commit")).toBe(false);
  });

  it("labels open deals by category and closed deals by stage", () => {
    expect(forecastCategoryLabel("PROPOSAL", "BEST_CASE")).toBe("Best case");
    expect(forecastCategoryLabel("QUALIFICATION", "COMMIT")).toBe("Commit");
    expect(forecastCategoryLabel("CLOSED_WON", null)).toBe("Closed");
    expect(forecastCategoryLabel("CLOSED_LOST", null)).toBe("Not forecast");
    // A stale category on a closed deal never wins over the stage.
    expect(forecastCategoryLabel("CLOSED_WON", "COMMIT")).toBe("Closed");
  });

  it("predicts the category after a move the same way the API sets it", () => {
    const commit = { stage: "PROPOSAL" as const, forecast_category: "COMMIT" as const };
    expect(forecastCategoryAfterMove(commit, "NEGOTIATION")).toBe("COMMIT");
    expect(forecastCategoryAfterMove(commit, "CLOSED_WON")).toBeNull();
    expect(forecastCategoryAfterMove(commit, "CLOSED_LOST")).toBeNull();
    const lost = { stage: "CLOSED_LOST" as const, forecast_category: null };
    expect(forecastCategoryAfterMove(lost, "QUALIFICATION")).toBe("PIPELINE");
    // A stale value on a closed deal never survives a reopen.
    expect(forecastCategoryAfterMove({ stage: "CLOSED_WON", forecast_category: "COMMIT" }, "PROPOSAL")).toBe(
      "PIPELINE",
    );
  });
});
