"use client";

import { useEffect, useRef, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
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
const PASSWORD_REQUIRED_MESSAGE =
  "This Google account needs the existing FlowPilot password to connect. Enter that password, then choose Continue with Google again.";
const PASSWORD_MISSING_MESSAGE =
  "Enter the existing FlowPilot password, then continue with Google again.";
const CONNECTION_FAILED_MESSAGE =
  "FlowPilot could not connect this Google account. You can continue with Google again, or sign in with email and password.";

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
  const [needsPassword, setNeedsPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [linkMessage, setLinkMessage] = useState<string | null>(null);
  const clientRef = useRef<GoogleCodeClient | null>(null);
  const inFlight = useRef(false);
  const needsPasswordRef = useRef(false);
  const passwordRef = useRef("");
  const callbackClaimed = useRef(false);
  const mountedRef = useRef(false);
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
            if (cancelled || callbackClaimed.current) return;
            callbackClaimed.current = true;
            const code = response.code;
            void (async () => {
              if (cancelled) return;
              if (response.error || !code) {
                onError("Google sign-in was cancelled.");
                inFlight.current = false;
                setPending(false);
                return;
              }
              const entered = needsPasswordRef.current ? passwordRef.current : "";
              const includePassword = entered.trim().length > 0;
              const body = includePassword ? { code, password: entered } : { code };
              try {
                const auth = await apiPost<AuthResponse>(
                  "/api/v1/auth/google",
                  body,
                  { token: null },
                );
                if (cancelled) return;
                needsPasswordRef.current = false;
                setNeedsPassword(false);
                setLinkMessage(null);
                onSuccess(auth);
              } catch (cause) {
                if (cancelled) return;
                if (cause instanceof ApiError && cause.status === 401) {
                  needsPasswordRef.current = true;
                  setNeedsPassword(true);
                  setLinkMessage(
                    includePassword
                      ? CONNECTION_FAILED_MESSAGE
                      : PASSWORD_REQUIRED_MESSAGE,
                  );
                  onError("");
                } else if (cause instanceof ApiError && cause.status === 503) {
                  needsPasswordRef.current = false;
                  setNeedsPassword(false);
                  setLinkMessage(null);
                  onError("Google sign-in is not configured.");
                } else {
                  needsPasswordRef.current = false;
                  setNeedsPassword(false);
                  setLinkMessage(null);
                  onError("Unable to continue with Google.");
                }
              } finally {
                if (includePassword) passwordRef.current = "";
                inFlight.current = false;
                if (!cancelled) {
                  if (includePassword) setPassword("");
                  setPending(false);
                }
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
      passwordRef.current = "";
      if (mountedRef.current) setPassword("");
    };
  }, [clientId, onError, onSuccess]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  function handleClick() {
    onError("");
    if (inFlight.current) return;
    if (!clientId) {
      onError("Google sign-in is not configured.");
      return;
    }
    if (!clientRef.current) {
      onError("Google sign-in is still loading.");
      return;
    }
    if (needsPasswordRef.current && passwordRef.current.trim() === "") {
      setLinkMessage(PASSWORD_MISSING_MESSAGE);
      return;
    }
    callbackClaimed.current = false;
    inFlight.current = true;
    setPending(true);
    clientRef.current.requestCode();
  }

  return (
    <>
      <button
        type="button"
        onClick={handleClick}
        disabled={pending || (Boolean(clientId) && !ready)}
        className="border-border bg-background text-foreground hover:bg-muted focus-visible:ring-ring inline-flex h-10 w-full items-center justify-center gap-3 rounded-lg border px-4 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60"
      >
        <GoogleMark />
        {pending ? "Continuing…" : "Continue with Google"}
      </button>
      {needsPassword ? (
        <div className="grid gap-3">
          <p id="google-link-password-message" className="text-danger-text text-sm" role="alert">
            {linkMessage}
          </p>
          <FormField
            label="Existing FlowPilot password"
            htmlFor="google-link-password"
            required
          >
            <Input
              id="google-link-password"
              type="password"
              autoComplete="current-password"
              aria-describedby="google-link-password-message"
              value={password}
              onChange={(event) => {
                passwordRef.current = event.target.value;
                setPassword(event.target.value);
              }}
              required
            />
          </FormField>
        </div>
      ) : null}
    </>
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
