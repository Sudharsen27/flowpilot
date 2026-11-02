import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ForecastAccuracyChart, ForecastAccuracyTable } from "@/components/forecast/forecast-accuracy-months";
import { accuracyFixture } from "@/test/forecast-accuracy-fixtures";
import type { ForecastAccuracyBasis } from "@/types/api";

function renderTable(lead = 0, basis: ForecastAccuracyBasis = "PROJECTED") {
  render(<ForecastAccuracyTable accuracy={accuracyFixture()} lead={lead} basis={basis} />);
  return screen.getByRole("table");
}

/** The desktop table row for a month; cells in column order. */
function cells(table: HTMLElement, monthName: string): string[] {
  const row = within(table)
    .getAllByRole("row")
    .find((candidate) => within(candidate).queryByText(monthName) !== null);
  if (!row) throw new Error(`No row for ${monthName}`);
  return within(row)
    .getAllByRole("cell")
    .map((cell) => cell.textContent ?? "");
}

describe("ForecastAccuracyTable", () => {
  it("shows a compared month exactly as returned, with signed variance", () => {
    const [, snapshot, forecast, actual, variance, accuracy] = cells(renderTable(), "September 2026");
    expect(snapshot).toContain("2026-08-31 00:05:00 UTC");
    expect(snapshot).toContain("Cutoff: before 2026-09-01 00:00:00 UTC");
    expect(forecast).toBe("₹1,20,000.00");
    expect(actual).toBe("₹1,00,000.001 deal");
    expect(variance).toBe("\u2212₹20,000.00\u221216.7%");
    expect(accuracy).toBe("80.0%");
  });

  it("shows negative accuracy as returned, never clamped", () => {
    const [, , , , variance, accuracy] = cells(renderTable(0, "BEST_CASE_SCENARIO"), "September 2026");
    expect(variance).toBe("\u2212₹2,00,000.00\u221266.7%");
    expect(accuracy).toBe("\u2212100.0%");
  });

  it("shows months before tracking without a forecast and never as 0", () => {
    const [, snapshot, forecast, , variance, accuracy] = cells(renderTable(), "August 2026");
    expect(snapshot).toContain("Before forecast tracking started");
    for (const value of [forecast, variance, accuracy]) {
      expect(value).toBe("—Not available");
    }
  });

  it("keeps variance but not accuracy when no revenue was won, and no percentage for a 0 forecast", () => {
    const [, , forecast, actual, variance, accuracy] = cells(renderTable(), "October 2026");
    expect(forecast).toBe("₹0.00");
    expect(actual).toBe("₹0.000 deals");
    expect(variance).toBe("₹0.00No %: forecast was 0");
    expect(accuracy).toBe("—No revenue won");
  });

  it("shows the month in progress with its forecast and revenue so far, unscored", () => {
    const table = renderTable();
    const [month, , forecast, actual, variance, accuracy] = cells(table, "November 2026");
    expect(month).toContain("In progress");
    expect(forecast).toBe("₹2,50,000.00");
    expect(actual).toBe("₹10,00,00,12,34,567.881 deal so far");
    expect(variance).toBe("—Not scored until month end");
    expect(accuracy).toBe("—Not scored until month end");
  });

  it("explains missing and other-currency snapshots at a longer lead", () => {
    const table = renderTable(30);
    const [, september] = cells(table, "September 2026");
    expect(september).toContain("No snapshot in the 7 days before the cutoff");
    expect(september).toContain("Cutoff: on or before 2026-08-02 00:00:00 UTC");
    const [, october, forecast] = cells(table, "October 2026");
    expect(october).toContain("2026-09-01 00:05:00 UTC");
    expect(october).toContain("Saved in another currency; not compared");
    expect(forecast).toBe("—Not available");
  });
});

describe("ForecastAccuracyChart", () => {
  it("names each month's values and replaces a missing forecast with its reason", () => {
    render(<ForecastAccuracyChart accuracy={accuracyFixture()} lead={0} basis="PROJECTED" />);
    const plot = screen.getByRole("group", { name: /^Won revenue and saved forecast by month/ });
    const names = within(plot)
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label"));
    expect(names).toEqual([
      "August 2026: Won revenue (actual) ₹1.5L, Saved forecast (estimate) Not tracked yet",
      "September 2026: Won revenue (actual) ₹1L, Saved forecast (estimate) ₹1.2L",
      "October 2026: Won revenue (actual) ₹0, Saved forecast (estimate) ₹0",
      expect.stringMatching(/^November 2026 \(in progress\): Won revenue \(actual\) .+ so far, Saved forecast \(estimate\) ₹2.5L$/),
    ]);
  });

  it("names the other-currency and missing snapshots at a longer lead", () => {
    render(<ForecastAccuracyChart accuracy={accuracyFixture()} lead={30} basis="PROJECTED" />);
    const labels = screen
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label") ?? "");
    expect(labels[1]).toMatch(/Saved forecast \(estimate\) No snapshot$/);
    expect(labels[2]).toMatch(/Saved forecast \(estimate\) Different currency$/);
  });
});
