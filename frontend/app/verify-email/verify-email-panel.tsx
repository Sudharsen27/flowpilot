"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { BrandLockup } from "@/components/brand-lockup";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { verifyEmail } from "@/lib/api/auth";

const INVALID_LINK = "This verification link is invalid or has expired.";
const TOO_MANY_ATTEMPTS = "Too many attempts. Try again later.";
const VALIDATION_ERROR = "This verification link could not be accepted.";
const GENERIC_ERROR = "Email verification could not be completed. Try again later.";

type Phase = "invalid" | "loading" | "verified" | "error";

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError) {
    if (cause.status === 400) return INVALID_LINK;
    if (cause.status === 429) return TOO_MANY_ATTEMPTS;
    if (cause.status === 422) return VALIDATION_ERROR;
  }
  return GENERIC_ERROR;
}

export function VerifyEmailPanel() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const submittedToken = useRef<string | null>(null);
  const [phase, setPhase] = useState<Phase>(token ? "loading" : "invalid");
  const [message, setMessage] = useState(INVALID_LINK);

  useEffect(() => {
    if (!token || submittedToken.current === token) return;
    submittedToken.current = token;
    let active = true;
    setPhase("loading");
    void verifyEmail(token)
      .then((response) => {
        if (!active) return;
        if (response.status === "verified") {
          setPhase("verified");
          return;
        }
        setMessage(GENERIC_ERROR);
        setPhase("error");
      })
      .catch((cause: unknown) => {
        if (!active) return;
        setMessage(errorMessage(cause));
        setPhase("error");
      });
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <main className="bg-background flex min-h-svh items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-lg gap-6">
        <BrandLockup />
        <Card>
          <CardHeader>
            <CardTitle>Verify your email</CardTitle>
            <CardDescription>
              {phase === "verified"
                ? "Your email is verified."
                : "Confirm this verification link to finish checking the address."}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            {phase === "loading" ? (
              <p className="text-muted-foreground text-sm" role="status">
                Verifying your email…
              </p>
            ) : null}
            {phase === "invalid" || phase === "error" ? (
              <p className="text-sm" role="alert">
                {message}
              </p>
            ) : null}
            {phase === "verified" ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                <Link href="/dashboard" className={buttonVariants({ className: "w-fit" })}>
                  Continue to workspace
                </Link>
                <Link
                  href="/login"
                  className={buttonVariants({ variant: "outline", className: "w-fit" })}
                >
                  Sign in
                </Link>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
