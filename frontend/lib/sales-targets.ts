/** URL state for the sales targets page: the year shown, as `?year=YYYY`. */

export const SALES_TARGETS_PATH = "/deals/targets";

const YEAR_PATTERN = /^\d{4}$/;
const MIN_YEAR = 1900;

/** The year in the URL, or `fallback` when it is missing or not a plausible year. */
export function parseSalesTargetsYear(searchParams: URLSearchParams, fallback: number): number {
  const raw = searchParams.get("year")?.trim() ?? "";
  if (!YEAR_PATTERN.test(raw)) return fallback;
  const year = Number.parseInt(raw, 10);
  return year >= MIN_YEAR ? year : fallback;
}

/** Link to the targets page for the year of a date-only string ("2026-11-01" → 2026). */
export function salesTargetsHref(dateOnly: string): string {
  const year = dateOnly.slice(0, 4);
  return YEAR_PATTERN.test(year) ? `${SALES_TARGETS_PATH}?year=${year}` : SALES_TARGETS_PATH;
}
