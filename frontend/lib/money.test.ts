import { describe, expect, it } from "vitest";

import {
  decimalEquals,
  formatDateOnly,
  formatMoney,
  formatMonth,
  parseAmountInput,
} from "@/lib/money";

describe("formatMoney", () => {
  it("formats INR with Indian grouping and exactly two decimals", () => {
    expect(formatMoney("125000.5", "INR")).toBe("₹1,25,000.50");
    expect(formatMoney("0.10", "INR")).toBe("₹0.10");
    expect(formatMoney("7", "INR")).toBe("₹7.00");
  });

  it("keeps the largest stored amount exact (no float rounding)", () => {
    expect(formatMoney("999999999999.99", "INR")).toBe("₹9,99,99,99,99,999.99");
    // A float would print 1000000000000.00 for this value.
    expect(formatMoney("9999999999999.99", "USD")).toBe("$9,999,999,999,999.99");
  });

  it("formats other currencies and falls back safely", () => {
    expect(formatMoney("1234.5", "USD")).toBe("$1,234.50");
    expect(formatMoney(null, "INR")).toBe("—");
    expect(formatMoney("abc", "INR")).toBe("INR abc");
    expect(formatMoney("12.3", "ZZZ")).toMatch(/12\.30$/);
  });
});

describe("parseAmountInput", () => {
  it("accepts the API's decimal format and strips grouping", () => {
    expect(parseAmountInput("125000.50")).toEqual({ ok: true, value: "125000.50" });
    expect(parseAmountInput(" 1,25,000.5 ")).toEqual({ ok: true, value: "125000.5" });
    expect(parseAmountInput("0")).toEqual({ ok: true, value: "0" });
    expect(parseAmountInput("999999999999.99")).toEqual({
      ok: true,
      value: "999999999999.99",
    });
  });

  it.each([
    ["", "Enter an amount."],
    ["-5", "Amount cannot be negative."],
    ["12.345", "Use at most 2 decimal places."],
    ["1000000000000", "Amount is too large."],
    ["1e5", "Enter a number such as 125000.50."],
    ["abc", "Enter a number such as 125000.50."],
  ])("rejects %j", (raw, error) => {
    expect(parseAmountInput(raw)).toEqual({ ok: false, error });
  });
});

describe("decimalEquals", () => {
  it("compares decimal strings exactly", () => {
    expect(decimalEquals("10", "10.00")).toBe(true);
    expect(decimalEquals("010.5", "10.50")).toBe(true);
    expect(decimalEquals("0", "0.00")).toBe(true);
    expect(decimalEquals("0.10", "0.1")).toBe(true);
    expect(decimalEquals("0.1", "0.10000000000000001")).toBe(false);
    expect(decimalEquals("999999999999.99", "999999999999.98")).toBe(false);
    expect(decimalEquals("abc", "abc")).toBe(false);
  });
});

describe("date formatting", () => {
  it("never shifts a date-only value across time zones", () => {
    expect(formatDateOnly("2026-12-01")).toBe("Dec 1, 2026");
    expect(formatDateOnly(null)).toBe("—");
    expect(formatMonth("2026-11-01")).toBe("November 2026");
  });
});
