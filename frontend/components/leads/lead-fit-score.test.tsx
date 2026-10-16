import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeadFitScorePanel } from "@/components/leads/lead-fit-score";
import type { LeadFitScore } from "@/types/api";

const score: LeadFitScore = {
  score: 75,
  confidence: 40,
  fit: "STRONG",
  configuration_valid: true,
  unavailable_criteria: { industry: "Not stored" },
  components: [
    {
      criterion: "company",
      status: "UNKNOWN",
      weight: 60,
      matched_terms: [],
      explanation: "This lead has no company information to assess.",
    },
    {
      criterion: "enquiry",
      status: "MATCHED",
      weight: 40,
      matched_terms: ["analytics"],
      explanation: "Matched configured enquiry term(s): analytics.",
    },
  ],
};

describe("LeadFitScorePanel", () => {
  it("shows the score, confidence, criterion reasons, and missing data", () => {
    render(<LeadFitScorePanel score={score} />);

    expect(screen.getByText("Strong · 75/100")).toBeVisible();
    expect(screen.getByText("Assessment confidence: 40%")).toBeVisible();
    expect(
      screen.getByText("This lead has no company information to assess."),
    ).toBeVisible();
    expect(
      screen.getByText("Matched configured enquiry term(s): analytics."),
    ).toBeVisible();
    expect(screen.getByText("Not assessed: Industry.")).toBeVisible();
  });

  it("labels an unassessable score as unknown", () => {
    render(<LeadFitScorePanel score={null} />);

    expect(screen.getByText("Unknown")).toBeVisible();
    expect(screen.getByText("Assessment confidence: 0%")).toBeVisible();
  });
});
