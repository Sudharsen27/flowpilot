"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useRef, useState } from "react";

import { AuthFrame } from "@/components/auth/auth-frame";
import {
  AuthDivider,
  GoogleContinueButton,
} from "@/components/auth/google-continue-button";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { requestVerificationEmail } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import type { AuthResponse } from "@/types/api";

const ACCEPTED_MESSAGE =
  "If verification is available for this account, an email will be sent shortly.";
const RESEND_ERROR_MESSAGE =
  "The verification email could not be requested. Try again.";

export default function LoginPage() {
  const router = useRouter();
  const { signIn, completeAuth } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const resendInFlight = useRef(false);
  const [resendPending, setResendPending] = useState(false);
  const [resendAccepted, setResendAccepted] = useState(false);
  const [resendError, setResendError] = useState<string | null>(null);

  const handleGoogleSuccess = useCallback(
    (auth: AuthResponse) => {
      completeAuth(auth);
      router.push("/dashboard");
    },
    [completeAuth, router],
  );

  const handleGoogleError = useCallback((message: string) => {
    setError(message || null);
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await signIn(email, password);
      router.push("/dashboard");
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 429) {
        setError("Too many attempts. Try again later.");
      } else if (cause instanceof ApiError) {
        setError("Invalid email or password.");
      } else {
        setError("Unable to sign in.");
      }
    } finally {
      setPending(false);
    }
  }

  async function resendVerification() {
    const address = email.trim();
    if (resendInFlight.current || !address) return;
    resendInFlight.current = true;
    setResendPending(true);
    setResendAccepted(false);
    setResendError(null);
    try {
      const response = await requestVerificationEmail(address);
      if (response.status !== "accepted") {
        setResendError(RESEND_ERROR_MESSAGE);
        return;
      }
      setResendAccepted(true);
    } catch {
      setResendError(RESEND_ERROR_MESSAGE);
    } finally {
      resendInFlight.current = false;
      setResendPending(false);
    }
  }

  return (
    <AuthFrame
      title="Sign in"
      description="Open your workspace to review what the agent prepared and approve anything that should be sent."
      footer={
        <>
          Need an organization?{" "}
          <Link
            className="text-foreground underline underline-offset-4"
            href="/register"
          >
            Create an account
          </Link>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <GoogleContinueButton
          onSuccess={handleGoogleSuccess}
          onError={handleGoogleError}
        />
        <AuthDivider />
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <FormField label="Email" htmlFor="email" required>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </FormField>
          <FormField label="Password" htmlFor="password" required>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </FormField>
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <Button type="submit" className="mt-1 h-10 w-full" disabled={pending}>
            {pending ? "Signing in…" : "Sign in"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-10 w-full"
            disabled={resendPending || !email.trim()}
            onClick={() => void resendVerification()}
          >
            {resendPending ? "Sending…" : "Resend verification email"}
          </Button>
          {resendAccepted ? (
            <p className="text-sm" role="status">
              {ACCEPTED_MESSAGE}
            </p>
          ) : null}
          {resendError ? (
            <p className="text-danger-text text-sm" role="alert">
              {resendError}
            </p>
          ) : null}
        </form>
      </div>
    </AuthFrame>
  );
}
