import { FORECAST_ACCURACY_QUERY_ROOT } from "@/lib/forecast";
import { formatMoney } from "@/lib/money";
import type {
  ForecastAccuracy,
  ForecastAccuracyBasis,
  ForecastAccuracyComparison,
  ForecastAccuracyLead,
  ForecastAccuracyMonth,
  ForecastAccuracySummary,
  ForecastSnapshotStatus,
} from "@/types/api";

/**
 * URL state, labels and selectors for the forecast accuracy page. Nothing here does
 * arithmetic on amounts or percentages: every figure is a string returned by the API.
 */

export const FORECAST_ACCURACY_PATH = "/forecast/accuracy";

/** Every lead is requested at once, so switching lead never needs another request. */
export const ACCURACY_LEADS = [0, 30, 60, 90] as const;
export type AccuracyLead = (typeof ACCURACY_LEADS)[number];

export const ACCURACY_BASES: readonly ForecastAccuracyBasis[] = [
  "PROJECTED",
  "COMMIT_SCENARIO",
  "BEST_CASE_SCENARIO",
];

/** Closed months shown; the API allows at most 24 months in total. */
export const ACCURACY_RANGE_OPTIONS = [3, 6, 12, 24] as const;
export const ACCURACY_DEFAULT_RANGE = 6;
const ACCURACY_MAX_MONTHS = 24;

export type ForecastAccuracyUrlState = {
  /** Number of closed months, ending with the last closed month. */
  range: number;
  /** Adds the month in progress, which is shown but never scored. */
  includeCurrent: boolean;
  lead: AccuracyLead;
  basis: ForecastAccuracyBasis;
};

export const DEFAULT_ACCURACY_STATE: ForecastAccuracyUrlState = {
  range: ACCURACY_DEFAULT_RANGE,
  includeCurrent: false,
  lead: 0,
  basis: "PROJECTED",
};

export function parseForecastAccuracySearchParams(searchParams: URLSearchParams): ForecastAccuracyUrlState {
  const range = Number(searchParams.get("range")?.trim());
  const lead = Number(searchParams.get("lead")?.trim());
  const basis = searchParams.get("basis")?.trim().toUpperCase() ?? "";
  return {
    range: (ACCURACY_RANGE_OPTIONS as readonly number[]).includes(range) ? range : ACCURACY_DEFAULT_RANGE,
    includeCurrent: searchParams.get("current") === "1",
    lead: (ACCURACY_LEADS as readonly number[]).includes(lead) ? (lead as AccuracyLead) : 0,
    basis: (ACCURACY_BASES as readonly string[]).includes(basis)
      ? (basis as ForecastAccuracyBasis)
      : "PROJECTED",
  };
}

/** Defaults are omitted so the plain /forecast/accuracy URL stays canonical. */
export function serializeForecastAccuracySearchParams(state: ForecastAccuracyUrlState): string {
  const query = new URLSearchParams();
  if (state.range !== ACCURACY_DEFAULT_RANGE) query.set("range", String(state.range));
  if (state.includeCurrent) query.set("current", "1");
  if (state.lead !== 0) query.set("lead", String(state.lead));
  if (state.basis !== "PROJECTED") query.set("basis", state.basis);
  return query.toString();
}

export type AccuracyMonthRange = { fromMonth: string | null; toMonth: string | null };

function monthStart(year: number, monthIndex: number): string {
  const date = new Date(Date.UTC(year, monthIndex, 1));
  return date.toISOString().slice(0, 10);
}

/**
 * The months to request. The default (6 closed months) sends none, so the server picks
 * them from its own clock. Otherwise the range ends with the last closed UTC month, or
 * the current one when it is included; the total never exceeds the API's 24 months.
 */
export function accuracyMonthRange(state: ForecastAccuracyUrlState, now: Date): AccuracyMonthRange {
  if (state.range === ACCURACY_DEFAULT_RANGE && !state.includeCurrent) {
    return { fromMonth: null, toMonth: null };
  }
  const year = now.getUTCFullYear();
  const month = now.getUTCMonth();
  const last = state.includeCurrent ? month : month - 1;
  const total = Math.min(state.range + (state.includeCurrent ? 1 : 0), ACCURACY_MAX_MONTHS);
  return { fromMonth: monthStart(year, last - (total - 1)), toMonth: monthStart(year, last) };
}

/** Cache key: the organization, then the exact months requested. */
export function forecastAccuracyQueryKey(organizationId: string | null, range: AccuracyMonthRange) {
  return [FORECAST_ACCURACY_QUERY_ROOT, organizationId, range] as const;
}

export const ACCURACY_RANGE_LABELS: Record<number, string> = {
  3: "Last 3 closed months",
  6: "Last 6 closed months",
  12: "Last 12 closed months",
  24: "Last 24 closed months",
};

export const ACCURACY_BASIS_LABELS: Record<ForecastAccuracyBasis, string> = {
  PROJECTED: "Projected",
  COMMIT_SCENARIO: "Commit scenario",
  BEST_CASE_SCENARIO: "Best case scenario",
};

export const ACCURACY_BASIS_HINTS: Record<ForecastAccuracyBasis, string> = {
  PROJECTED: "Won plus probability-weighted open deals",
  COMMIT_SCENARIO: "Won plus full Commit amounts",
  BEST_CASE_SCENARIO: "Commit scenario plus full Best case amounts",
};

export function accuracyBasisLabel(basis: string): string {
  return ACCURACY_BASIS_LABELS[basis as ForecastAccuracyBasis] ?? basis;
}

/** "Month start" for lead 0, otherwise "30 days before". */
export function accuracyLeadLabel(lead: number): string {
  return lead === 0 ? "Month start" : `${lead} days before`;
}

/** Short form for compact controls: "Month start", "30 days". */
export function accuracyLeadShortLabel(lead: number): string {
  return lead === 0 ? "Month start" : `${lead} days`;
}

/** Why a lead has no comparison; null when it was compared. */
export function snapshotStatusText(status: ForecastSnapshotStatus | string, toleranceDays: number): string | null {
  switch (status) {
    case "AVAILABLE":
      return null;
    case "MISSING":
      return `No snapshot in the ${toleranceDays} days before the cutoff`;
    case "BEFORE_FIRST_SNAPSHOT":
      return "Before forecast tracking started";
    case "CURRENCY_MISMATCH":
      return "Saved in another currency; not compared";
    default:
      return status;
  }
}

/** Short reason for a chart tooltip. */
export function snapshotStatusShortText(status: ForecastSnapshotStatus | string): string {
  switch (status) {
    case "MISSING":
      return "No snapshot";
    case "BEFORE_FIRST_SNAPSHOT":
      return "Not tracked yet";
    case "CURRENCY_MISMATCH":
      return "Different currency";
    default:
      return status;
  }
}

export function leadOf(month: ForecastAccuracyMonth, lead: number): ForecastAccuracyLead | undefined {
  return month.forecasts.find((entry) => entry.lead_days === lead);
}

export function comparisonOf(
  lead: ForecastAccuracyLead | undefined,
  basis: ForecastAccuracyBasis,
): ForecastAccuracyComparison | undefined {
  return lead?.comparisons.find((entry) => entry.basis === basis);
}

export function summaryOf(
  accuracy: ForecastAccuracy,
  lead: number,
  basis: ForecastAccuracyBasis,
): ForecastAccuracySummary | undefined {
  return accuracy.summary.find((entry) => entry.lead_days === lead && entry.basis === basis);
}

/** Closed months in the range: the months that can be scored. */
export function closedMonthCount(accuracy: ForecastAccuracy): number {
  return accuracy.months.filter((month) => month.status === "CLOSED").length;
}

/** Months whose snapshot for any requested lead is in another currency. */
export function currencyMismatchMonths(accuracy: ForecastAccuracy): ForecastAccuracyMonth[] {
  return accuracy.months.filter((month) =>
    month.forecasts.some((lead) => lead.snapshot_status === "CURRENCY_MISMATCH"),
  );
}

/** True when some month predates tracking for the lead (tracking started inside the range). */
export function hasMonthsBeforeTracking(accuracy: ForecastAccuracy, lead: number): boolean {
  return accuracy.months.some((month) => leadOf(month, lead)?.snapshot_status === "BEFORE_FIRST_SNAPSHOT");
}

const MINUS = "\u2212";

/** A typographic minus for display; the API's string is otherwise shown as returned. */
function withMinus(value: string): string {
  return value.startsWith("-") ? `${MINUS}${value.slice(1)}` : value;
}

function isZero(value: string): boolean {
  return /^-?0+(\.0+)?$/.test(value.trim());
}

/** "+12.5%", "−3.0%" or "0.0%"; null stays null. */
export function formatSignedPercent(value: string | null): string | null {
  if (value === null) return null;
  if (value.startsWith("-")) return `${withMinus(value)}%`;
  return isZero(value) ? `${value}%` : `+${value}%`;
}

/** Accuracy as returned, with a typographic minus when negative: "83.7%", "−2800.0%". */
export function formatAccuracyPercent(value: string | null): string | null {
  return value === null ? null : `${withMinus(value)}%`;
}

/** Variance money with an explicit sign: "+₹1,000.00", "−₹495.00", "₹0.00". */
export function formatSignedMoney(amount: string | null, currency: string): string | null {
  if (amount === null) return null;
  if (amount.startsWith("-")) return `${MINUS}${formatMoney(amount.slice(1), currency)}`;
  return isZero(amount) ? formatMoney(amount, currency) : `+${formatMoney(amount, currency)}`;
}
