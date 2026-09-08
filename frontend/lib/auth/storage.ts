const TOKEN_KEY = "flowpilot.access_token";
export const AUTH_SESSION_INVALIDATED_EVENT = "flowpilot:session-invalidated";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event(AUTH_SESSION_INVALIDATED_EVENT));
}
