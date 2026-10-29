/**
 * Exact money handling. Amounts stay decimal strings end to end; nothing here
 * converts them to a float.
 */

/** Mirrors the API: non-negative, at most 12 whole digits and 2 decimals. */
const AMOUNT_PATTERN = /^\d{1,12}(\.\d{1,2})?$/;
const DECIMAL_PATTERN = /^(-?)(\d+)(?:\.(\d+))?$/;

export type AmountInputResult = { ok: true; value: string } | { ok: false; error: string };

/** Validate what a person typed. Grouping commas and spaces are ignored. */
export function parseAmountInput(raw: string): AmountInputResult {
  const cleaned = raw.replace(/[,\s]/g, "");
  if (!cleaned) return { ok: false, error: "Enter an amount." };
  if (cleaned.startsWith("-")) return { ok: false, error: "Amount cannot be negative." };
  if (!/^\d+(\.\d+)?$/.test(cleaned)) {
    return { ok: false, error: "Enter a number such as 125000.50." };
  }
  if (!AMOUNT_PATTERN.test(cleaned)) {
    const [whole, fraction = ""] = cleaned.split(".");
    if (fraction.length > 2) {
      return { ok: false, error: "Use at most 2 decimal places." };
    }
    if (whole.replace(/^0+(?=\d)/, "").length > 12) {
      return { ok: false, error: "Amount is too large." };
    }
  }
  return { ok: true, value: cleaned };
}

/** Exact decimal equality without floats: "10" equals "10.00"; "010.5" equals "10.50". */
export function decimalEquals(a: string, b: string): boolean {
  const normalize = (value: string) => {
    const match = DECIMAL_PATTERN.exec(value.trim());
    if (!match) return null;
    const [, sign, whole, fraction = ""] = match;
    const digits = whole.replace(/^0+(?=\d)/, "");
    const cents = fraction.replace(/0+$/, "");
    const zero = /^0+$/.test(whole) && cents === "";
    return `${zero ? "" : sign}${digits}.${cents}`;
  };
  const left = normalize(a);
  return left !== null && left === normalize(b);
}

function localeFor(currency: string) {
  return currency === "INR" ? "en-IN" : "en";
}

/**
 * Format an API amount such as "1234567.5" as "₹12,34,567.50". The whole part is
 * grouped through BigInt, so precision never depends on floating point.
 */
export function formatMoney(amount: string | null | undefined, currency: string): string {
  if (amount === null || amount === undefined) return "—";
  const match = DECIMAL_PATTERN.exec(amount.trim());
  if (!match) return `${currency} ${amount}`;
  const [, sign, whole, fraction = ""] = match;
  const cents = `${fraction}00`.slice(0, 2);
  try {
    const parts = new Intl.NumberFormat(localeFor(currency), {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
      minimumFractionDigits: 0,
    }).formatToParts(BigInt(whole));
    const decimal =
      new Intl.NumberFormat(localeFor(currency))
        .formatToParts(1.5)
        .find((part) => part.type === "decimal")?.value ?? ".";
    let output = "";
    parts.forEach((part, index) => {
      output += part.value;
      const next = parts[index + 1];
      if (part.type === "integer" && next?.type !== "group" && next?.type !== "integer") {
        output += `${decimal}${cents}`;
      }
    });
    return `${sign}${output}`;
  } catch {
    return `${sign}${currency} ${whole}.${cents}`;
  }
}

/** Format a date-only API value ("2026-12-15") without shifting it across time zones. */
export function formatDateOnly(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeZone: "UTC" }).format(date);
}

/** "2026-11-01" → "November 2026". */
export function formatMonth(periodStart: string): string {
  const date = new Date(`${periodStart}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return periodStart;
  return new Intl.DateTimeFormat("en", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}
