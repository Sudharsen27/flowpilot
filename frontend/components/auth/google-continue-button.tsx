"use client";

import { useEffect, useRef, useState } from "react";

import { ApiError, apiPost } from "@/lib/api/client";
import type { AuthResponse } from "@/types/api";

type GoogleCodeClient = {
  requestCode: () => void;
};

type GoogleAccounts = {
  oauth2: {
    initCodeClient: (config: {
      client_id: string;
      scope: string;
      ux_mode: "popup";
      callback: (response: { code?: string; error?: string }) => void;
    }) => GoogleCodeClient;
  };
};

declare global {
  interface Window {
    google?: { accounts: GoogleAccounts };
  }
}

const SCRIPT_ID = "flowpilot-google-gsi";
const SCRIPT_SRC = "https://accounts.google.com/gsi/client";

function googleClientId() {
  return process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim() || "";
}

function loadGoogleScript(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.google?.accounts?.oauth2) return Promise.resolve();
  const existing = document.getElementById(SCRIPT_ID);
  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("load failed")), {
        once: true,
      });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = SCRIPT_SRC;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("load failed"));
    document.head.appendChild(script);
  });
}

export function GoogleContinueButton({
  onSuccess,
  onError,
}: {
  onSuccess: (auth: AuthResponse) => void;
  onError: (message: string) => void;
}) {
  const [pending, setPending] = useState(false);
  const [ready, setReady] = useState(false);
  const clientRef = useRef<GoogleCodeClient | null>(null);
  const clientId = googleClientId();

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    void loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google?.accounts?.oauth2) return;
        clientRef.current = window.google.accounts.oauth2.initCodeClient({
          client_id: clientId,
          scope: "openid email profile",
          ux_mode: "popup",
          callback: (response) => {
            void (async () => {
              if (response.error || !response.code) {
                onError("Google sign-in was cancelled.");
                setPending(false);
                return;
              }
              try {
                const auth = await apiPost<AuthResponse>(
                  "/api/v1/auth/google",
                  { code: response.code },
                  { token: null },
                );
                onSuccess(auth);
              } catch (cause) {
                onError(
                  cause instanceof ApiError && cause.status === 503
                    ? "Google sign-in is not configured."
                    : "Unable to continue with Google.",
                );
              } finally {
                setPending(false);
              }
            })();
          },
        });
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (!cancelled) onError("Google sign-in could not be loaded.");
      });
    return () => {
      cancelled = true;
    };
  }, [clientId, onError, onSuccess]);

  function handleClick() {
    onError("");
    if (!clientId) {
      onError("Google sign-in is not configured.");
      return;
    }
    if (!clientRef.current) {
      onError("Google sign-in is still loading.");
      return;
    }
    setPending(true);
    clientRef.current.requestCode();
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={pending || (Boolean(clientId) && !ready)}
      className="border-border bg-background text-foreground hover:bg-muted focus-visible:ring-ring inline-flex h-10 w-full items-center justify-center gap-3 rounded-lg border px-4 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
    >
      <GoogleMark />
      {pending ? "Continuing…" : "Continue with Google"}
    </button>
  );
}

function GoogleMark() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 48 48">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.2 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.5-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.1 8 3l5.7-5.7C34.2 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.1 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-8l-6.5 5C9.6 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4.1 5.5l.1.1 6.2 5.2C39.2 36.3 44 31 44 24c0-1.3-.1-2.5-.4-3.5z"
      />
    </svg>
  );
}

export function AuthDivider() {
  return (
    <div className="relative my-1 flex items-center gap-3" aria-hidden="true">
      <span className="border-border h-px flex-1 border-t" />
      <span className="text-muted-foreground text-xs tracking-wide uppercase">or</span>
      <span className="border-border h-px flex-1 border-t" />
    </div>
  );
}
