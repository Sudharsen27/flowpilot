export const AUTH_SESSION_INVALIDATED_EVENT = "flowpilot:session-invalidated";

export function invalidateAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new Event(AUTH_SESSION_INVALIDATED_EVENT));
}
