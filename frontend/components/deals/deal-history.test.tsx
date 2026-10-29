import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DealHistoryList } from "@/components/deals/deal-history";
import type { DealHistoryEvent } from "@/types/api";

function event(overrides: Partial<DealHistoryEvent>): DealHistoryEvent {
  return {
    id: "e1",
    deal_id: "deal-1",
    changes: ["STAGE"],
    previous_stage: "DISCOVERY",
    new_stage: "PROPOSAL",
    previous_amount: "100.00",
    new_amount: "100.00",
    previous_expected_close_date: "2026-12-01",
    new_expected_close_date: "2026-12-01",
    previous_probability: null,
    new_probability: null,
    is_correction: false,
    changed_by_user_id: "user-1",
    changed_by_name: "Olivia Owner",
    change_reason: null,
    created_at: "2026-10-20T10:00:00Z",
    ...overrides,
  };
}

function entries() {
  return within(screen.getByRole("list", { name: "Deal history, oldest first" }))
    .getAllByRole("listitem")
    .filter((item) => item.parentElement?.tagName === "OL");
}

describe("DealHistoryList", () => {
  it("describes override changes, including resets to the stage default", () => {
    render(
      <DealHistoryList
        currency="INR"
        events={[
          event({
            id: "p1",
            changes: ["PROBABILITY"],
            previous_stage: "PROPOSAL",
            previous_probability: 35,
            new_probability: 40,
          }),
          event({
            id: "p2",
            changes: ["STAGE", "PROBABILITY"],
            previous_stage: "PROPOSAL",
            new_stage: "NEGOTIATION",
            previous_probability: 40,
            new_probability: null,
          }),
          event({
            id: "p3",
            changes: ["PROBABILITY"],
            previous_stage: "NEGOTIATION",
            new_stage: "NEGOTIATION",
            previous_probability: null,
            new_probability: 90,
          }),
        ]}
      />,
    );
    const [first, second, third] = entries();
    expect(first).toHaveTextContent(
      "Probability changed from 35% (override) to 40% (override).",
    );
    expect(second).toHaveTextContent("Stage moved from Proposal to Negotiation.");
    expect(second).toHaveTextContent(
      "Probability changed from 40% (override) to the stage default.",
    );
    expect(third).toHaveTextContent(
      "Probability changed from the stage default to 90% (override).",
    );
    expect(screen.queryByText("Correction")).not.toBeInTheDocument();
  });

  it("marks amount corrections with a badge and the correction reason", () => {
    render(
      <DealHistoryList
        currency="INR"
        events={[
          event({
            id: "c1",
            changes: ["AMOUNT"],
            previous_stage: "CLOSED_WON",
            new_stage: "CLOSED_WON",
            previous_amount: "120000.00",
            new_amount: "118500.00",
            is_correction: true,
            change_reason: "Invoice issued with a discount",
            changed_by_name: "Ada Admin",
          }),
          event({
            id: "a1",
            changes: ["AMOUNT"],
            previous_stage: "PROPOSAL",
            previous_amount: "1.00",
            new_amount: "2.00",
            change_reason: "Scope grew",
          }),
        ]}
      />,
    );
    const [correction, ordinary] = entries();
    expect(within(correction!).getByText("Correction")).toBeInTheDocument();
    expect(correction).toHaveTextContent("Amount corrected from ₹1,20,000.00 to ₹1,18,500.00.");
    expect(correction).toHaveTextContent("Correction reason: Invoice issued with a discount");
    expect(correction).toHaveTextContent("by Ada Admin");
    expect(within(ordinary!).queryByText("Correction")).not.toBeInTheDocument();
    expect(ordinary).toHaveTextContent("Amount changed from ₹1.00 to ₹2.00.");
    expect(ordinary).toHaveTextContent("Reason: Scope grew");
    expect(ordinary).not.toHaveTextContent("Correction reason");
  });

  it("renders rows recorded before probability history without new fields", () => {
    const legacy = event({ id: "old", changes: ["AMOUNT"], previous_amount: "5.00" });
    delete legacy.previous_probability;
    delete legacy.new_probability;
    delete legacy.is_correction;
    render(<DealHistoryList currency="INR" events={[legacy]} />);
    const [row] = entries();
    expect(row).toHaveTextContent("Amount changed from ₹5.00 to ₹100.00.");
    expect(row).not.toHaveTextContent("Probability");
    expect(screen.queryByText("Correction")).not.toBeInTheDocument();
  });

  it("never renders an entry without a description", () => {
    const unknown = event({
      id: "u1",
      changes: ["FUTURE_CHANGE" as DealHistoryEvent["changes"][number]],
    });
    render(<DealHistoryList currency="INR" events={[unknown]} />);
    expect(entries()[0]).toHaveTextContent("Deal details were updated.");
  });

  it("describes forecast category changes, reading closed deals from their stage", () => {
    render(
      <DealHistoryList
        currency="INR"
        events={[
          event({
            id: "c0",
            changes: ["CREATED"],
            previous_stage: null,
            new_stage: "DISCOVERY",
            previous_amount: null,
            previous_expected_close_date: null,
            new_forecast_category: "PIPELINE",
          }),
          event({
            id: "c1",
            changes: ["FORECAST_CATEGORY"],
            previous_stage: "DISCOVERY",
            new_stage: "DISCOVERY",
            previous_forecast_category: "PIPELINE",
            new_forecast_category: "COMMIT",
          }),
          event({
            id: "c2",
            changes: ["STAGE", "FORECAST_CATEGORY"],
            previous_stage: "DISCOVERY",
            new_stage: "CLOSED_WON",
            previous_forecast_category: "COMMIT",
            new_forecast_category: null,
          }),
          event({
            id: "c3",
            changes: ["STAGE", "FORECAST_CATEGORY"],
            previous_stage: "CLOSED_WON",
            new_stage: "PROPOSAL",
            previous_forecast_category: null,
            new_forecast_category: "PIPELINE",
          }),
        ]}
      />,
    );
    const [created, changed, closed, reopened] = entries();
    expect(created).toHaveTextContent("Forecast category: Pipeline.");
    expect(changed).toHaveTextContent("Forecast category changed from Pipeline to Commit.");
    expect(closed).toHaveTextContent("Forecast category changed from Commit to Closed.");
    expect(reopened).toHaveTextContent("Forecast category changed from Closed to Pipeline.");
  });

  it("does not invent a category for rows recorded before categories existed", () => {
    render(
      <DealHistoryList
        currency="INR"
        events={[
          event({
            id: "old",
            changes: ["CREATED"],
            previous_stage: null,
            previous_amount: null,
            previous_expected_close_date: null,
          }),
        ]}
      />,
    );
    expect(entries()[0]).not.toHaveTextContent("Forecast category");
  });
});
