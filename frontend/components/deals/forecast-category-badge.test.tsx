import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ForecastCategoryBadge } from "@/components/deals/forecast-category-badge";
import type { DealStage, ForecastCategory } from "@/types/api";

function badge(stage: DealStage, category: ForecastCategory | null) {
  const { container } = render(<ForecastCategoryBadge stage={stage} category={category} />);
  return container.querySelector("[data-slot=forecast-category-badge]") as HTMLElement;
}

describe("ForecastCategoryBadge", () => {
  it.each([
    ["PIPELINE", "Pipeline"],
    ["BEST_CASE", "Best case"],
    ["COMMIT", "Commit"],
  ] as const)("shows %s on an open deal", (category, label) => {
    const element = badge("PROPOSAL", category);
    expect(element).toHaveTextContent(label);
    expect(element).toHaveAttribute("data-category", category);
  });

  it("derives Closed for won deals and Not forecast for lost deals", () => {
    expect(badge("CLOSED_WON", null)).toHaveAttribute("data-category", "CLOSED");
    expect(screen.getByText("Closed")).toBeInTheDocument();
    expect(badge("CLOSED_LOST", null)).toHaveTextContent("Not forecast");
  });

  it("is styled apart from the coloured stage badge", () => {
    const element = badge("NEGOTIATION", "COMMIT");
    expect(element).not.toHaveAttribute("data-slot", "status-badge");
    expect(element.className).toContain("border-border");
    // The icon is decorative; the text is the accessible label.
    expect(element.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});
