"use client";

import Link from "next/link";
import { useRef, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { requestVerificationEmail } from "@/lib/api/auth";

const ACCEPTED_MESSAGE =
  "If verification is available for this account, an email will be sent shortly.";
const RESEND_ERROR_MESSAGE =
  "The verification email could not be requested. Try again.";

export default function VerificationPendingPage() {
  const { session } = useAuth();
  const email = session?.user.email;
  const requestInFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function resend() {
    if (requestInFlight.current || !email) return;
    requestInFlight.current = true;
    setPending(true);
    setAccepted(false);
    setError(null);
    try {
      const response = await requestVerificationEmail(email);
      if (response.status !== "accepted") {
        setError(RESEND_ERROR_MESSAGE);
        return;
      }
      setAccepted(true);
    } catch {
      setError(RESEND_ERROR_MESSAGE);
    } finally {
      requestInFlight.current = false;
      setPending(false);
    }
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="Verify your email"
        description="Your account is signed in. Email verification for this address is still pending."
      />
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Verification pending</CardTitle>
          <CardDescription>
            You can continue into the workspace now. Verification does not
            block access to your organization.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {email ? (
            <p>
              <span className="text-muted-foreground text-sm">Account email</span>
              <span className="mt-1 block font-medium break-all">{email}</span>
            </p>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <Button
              type="button"
              variant="outline"
              disabled={pending || !email}
              onClick={() => void resend()}
            >
              {pending ? "Sending…" : "Resend verification email"}
            </Button>
            <Link
              href="/dashboard"
              className={buttonVariants({ className: "w-fit" })}
            >
              Continue to workspace
            </Link>
          </div>
          {accepted ? (
            <p className="text-sm" role="status">
              {ACCEPTED_MESSAGE}
            </p>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
