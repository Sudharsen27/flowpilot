/**
 * Fired after every deal write the browser sends, whether or not it succeeded: a
 * request that failed on the way back may still have been saved. Listeners refresh
 * figures derived from deals, such as the cached forecast.
 */
export const DEALS_CHANGED_EVENT = "flowpilot:deals-changed";

export function notifyDealsChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(DEALS_CHANGED_EVENT));
}

/**
 * Fired after every sales target save the browser sends, whether or not it succeeded.
 * Only the forecast compares against targets, so only it is refreshed.
 */
export const SALES_TARGETS_CHANGED_EVENT = "flowpilot:sales-targets-changed";

export function notifySalesTargetsChanged(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(SALES_TARGETS_CHANGED_EVENT));
}
