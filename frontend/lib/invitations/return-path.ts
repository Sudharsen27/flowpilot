const ACCEPT_PATH = "/invitations/accept";

/** Only an in-app invitation link may be used as a post-login return path. */
export function invitationReturnPath(raw: string | null | undefined): string | null {
  if (!raw || raw.startsWith("//")) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(raw, "https://flowpilot.invalid");
  } catch {
    return null;
  }
  if (url.origin !== "https://flowpilot.invalid" || url.pathname !== ACCEPT_PATH) {
    return null;
  }
  const token = url.searchParams.get("token")?.trim() ?? "";
  if (!token || [...url.searchParams.keys()].some((key) => key !== "token")) {
    return null;
  }
  return `${ACCEPT_PATH}?token=${encodeURIComponent(token)}`;
}

export function currentInvitationReturnPath(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return invitationReturnPath(new URLSearchParams(window.location.search).get("next"));
}

export function loginPathForInvitation(token: string): string {
  const next = invitationReturnPath(`${ACCEPT_PATH}?token=${token}`);
  if (!next) {
    return "/login";
  }
  return `/login?next=${encodeURIComponent(next)}`;
}

/** Keep the current invitation return path on login and account creation. */
export function pathWithInvitationReturn(path: "/login" | "/register"): string {
  const next = currentInvitationReturnPath();
  if (!next) {
    return path;
  }
  return `${path}?next=${encodeURIComponent(next)}`;
}
