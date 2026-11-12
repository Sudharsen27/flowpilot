"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

import { BrandLockup } from "@/components/brand-lockup";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { confirmPasswordReset } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;
const INVALID_LINK = "This password reset link is invalid or has expired.";
const TOO_MANY_ATTEMPTS = "Too many attempts. Try again later.";
const VALIDATION_ERROR = "This password could not be accepted.";
const GENERIC_ERROR = "The password could not be reset. Try again.";
const MISMATCH = "Passwords do not match.";
const TOO_SHORT = "Use at least 8 characters.";

type Phase = "invalid" | "form" | "success" | "error";

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 400) return INVALID_LINK;
    if (cause.status === 429) return TOO_MANY_ATTEMPTS;
    if (cause.status === 422) return VALIDATION_ERROR;
  }
  return GENERIC_ERROR;
}

export function ResetPasswordPanel() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const submitInFlight = useRef(false);
  const [phase, setPhase] = useState<Phase>(token ? "form" : "invalid");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState(INVALID_LINK);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitInFlight.current || !token || phase === "success") return;
    if (password.length < MIN_PASSWORD_LENGTH) {
      setMessage(TOO_SHORT);
      setPhase("error");
      return;
    }
    if (password.length > MAX_PASSWORD_LENGTH) {
      setMessage("Use at most 128 characters.");
      setPhase("error");
      return;
    }
    if (password !== confirmation) {
      setMessage(MISMATCH);
      setPhase("error");
      return;
    }
    submitInFlight.current = true;
    setPending(true);
    setPhase("form");
    try {
      const response = await confirmPasswordReset(token, password);
      if (response.status !== "reset") {
        setMessage(GENERIC_ERROR);
        setPhase("error");
        return;
      }
      setPhase("success");
    } catch (cause) {
      setMessage(errorMessage(cause));
      setPhase("error");
    } finally {
      submitInFlight.current = false;
      setPending(false);
    }
  }

  return (
    <main className="bg-background flex min-h-svh items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-lg gap-6">
        <BrandLockup />
        <Card>
          <CardHeader>
            <CardTitle>Reset your password</CardTitle>
            <CardDescription>
              {phase === "success"
                ? "Your password has been reset."
                : "Choose a new password for your account."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {phase === "invalid" || phase === "error" ? (
              <p className="text-sm" role="alert">
                {message}
              </p>
            ) : null}
            {phase === "success" ? (
              <Link
                href="/login"
                className={buttonVariants({ className: "w-fit" })}
              >
                Sign in
              </Link>
            ) : null}
            {token && phase !== "success" ? (
              <form className="grid gap-4" onSubmit={(event) => void handleSubmit(event)}>
                <FormField label="New password" htmlFor="new-password" required>
                  <Input
                    id="new-password"
                    type="password"
                    autoComplete="new-password"
                    minLength={MIN_PASSWORD_LENGTH}
                    maxLength={MAX_PASSWORD_LENGTH}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </FormField>
                <FormField label="Confirm new password" htmlFor="confirm-password" required>
                  <Input
                    id="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    minLength={MIN_PASSWORD_LENGTH}
                    maxLength={MAX_PASSWORD_LENGTH}
                    value={confirmation}
                    onChange={(event) => setConfirmation(event.target.value)}
                    required
                  />
                </FormField>
                <Button type="submit" className="h-10 w-full" disabled={pending}>
                  {pending ? "Resetting…" : "Reset password"}
                </Button>
              </form>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
