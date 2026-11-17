"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useRef, useState } from "react";

import { AuthFrame } from "@/components/auth/auth-frame";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { apiErrorDetail } from "@/lib/api/error-detail";
import { logoutSession } from "@/lib/api/auth";
import { acceptInvitation } from "@/lib/api/invitations";
import { loginPathForInvitation } from "@/lib/invitations/return-path";
import type { AuthResponse, InvitationAcceptResponse } from "@/types/api";

type Phase =
  | { kind: "ready" }
  | { kind: "missing" }
  | { kind: "new-user" }
  | { kind: "sign-in" }
  | { kind: "joined"; organizationId: string }
  | { kind: "mismatch" }
  | { kind: "invalid"; message: string };

function isSessionResponse(
  response: InvitationAcceptResponse,
): response is AuthResponse {
  return "access_token" in response && "user" in response && "organization" in response;
}

export function InvitationAcceptPanel() {
  const router = useRouter();
  const { completeAuth, switchOrganization } = useAuth();
  const searchParams = useSearchParams();
  const token = searchParams.get("token")?.trim() ?? "";
  const [phase, setPhase] = useState<Phase>(token ? { kind: "ready" } : { kind: "missing" });
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);

  function enterInvitedSession(response: AuthResponse) {
    completeAuth(response);
    router.replace("/dashboard");
  }

  function applyProbe(response: InvitationAcceptResponse) {
    if (isSessionResponse(response)) {
      enterInvitedSession(response);
      return;
    }
    if (response.status === "sign_in_required") {
      setPhase({ kind: "sign-in" });
      return;
    }
    setPhase({ kind: "joined", organizationId: response.organization_id });
  }

  function applyProbeError(cause: unknown) {
    const detail = apiErrorDetail(cause, "");
    if (detail === "Name and password are required") {
      setPhase({ kind: "new-user" });
      return;
    }
    if (detail === "This invitation does not match the signed-in account.") {
      setPhase({ kind: "mismatch" });
      return;
    }
    setPhase({
      kind: "invalid",
      message: detail || "This invitation link is invalid or has expired.",
    });
  }

  async function continueWithInvitation() {
    if (!token || submitting.current) {
      return;
    }
    submitting.current = true;
    setPending(true);
    setError(null);
    try {
      applyProbe(await acceptInvitation({ token }));
    } catch (cause) {
      applyProbeError(cause);
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || submitting.current) {
      return;
    }
    submitting.current = true;
    setPending(true);
    setError(null);
    try {
      const response = await acceptInvitation({
        token,
        name: name.trim(),
        password,
      });
      if (!isSessionResponse(response)) {
        setError("The invitation could not be accepted. Try again.");
        return;
      }
      enterInvitedSession(response);
    } catch (cause) {
      setError(apiErrorDetail(cause, "The invitation could not be accepted. Try again."));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  async function switchToInvitedOrganization(organizationId: string) {
    setSwitching(true);
    setError(null);
    try {
      await switchOrganization(organizationId);
      router.replace("/dashboard");
    } catch (cause) {
      setError(
        apiErrorDetail(cause, "The organization could not be switched. Try again."),
      );
    } finally {
      setSwitching(false);
    }
  }

  async function signOutAndReturn() {
    try {
      await logoutSession();
    } catch {
      // The login page can still replace this browser session.
    }
    router.replace(loginPathForInvitation(token));
  }

  let body = (
    <div className="grid gap-4">
      <p className="text-sm">
        Continue to accept this invitation. The invitation chooses your role.
      </p>
      <Button
        type="button"
        className="h-10 w-full"
        disabled={pending}
        onClick={() => void continueWithInvitation()}
      >
        {pending ? "Checking…" : "Accept invitation"}
      </Button>
    </div>
  );
  if (phase.kind === "missing" || phase.kind === "invalid") {
    body = (
      <p className="text-danger-text text-sm" role="alert">
        {phase.kind === "invalid"
          ? phase.message
          : "This invitation link is invalid or has expired."}
      </p>
    );
  } else if (phase.kind === "sign-in") {
    body = (
      <div className="grid gap-4">
        <p className="text-sm">
          This invitation belongs to an existing account. Sign in with that email, including
          Google if that is how the account was created. A password is not created here.
        </p>
        <Button render={<Link href={loginPathForInvitation(token)} />}>
          Sign in to accept
        </Button>
      </div>
    );
  } else if (phase.kind === "mismatch") {
    body = (
      <div className="grid gap-4">
        <p className="text-danger-text text-sm" role="alert">
          This invitation does not match the signed-in account.
        </p>
        <Button type="button" variant="outline" onClick={() => void signOutAndReturn()}>
          Sign out and use the invited account
        </Button>
      </div>
    );
  } else if (phase.kind === "joined") {
    body = (
      <div className="grid gap-4">
        <p className="text-sm" role="status">
          You joined the organization. Switch now to open that workspace, or stay in your
          current one.
        </p>
        {error ? (
          <p className="text-danger-text text-sm" role="alert">
            {error}
          </p>
        ) : null}
        <Button
          type="button"
          className="h-10 w-full"
          disabled={switching}
          onClick={() => void switchToInvitedOrganization(phase.organizationId)}
        >
          {switching ? "Switching…" : "Switch to this organization"}
        </Button>
        <Button render={<Link href="/dashboard" />} variant="outline">
          Stay in current workspace
        </Button>
      </div>
    );
  } else if (phase.kind === "new-user") {
    body = (
      <form className="flex flex-col gap-4" onSubmit={(event) => void createAccount(event)}>
        <FormField label="Name" htmlFor="invite-name" required>
          <Input
            id="invite-name"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </FormField>
        <FormField label="Password" htmlFor="invite-password" required>
          <Input
            id="invite-password"
            type="password"
            autoComplete="new-password"
            minLength={8}
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
        <Button type="submit" className="h-10 w-full" disabled={pending}>
          {pending ? "Creating account…" : "Create account and join"}
        </Button>
      </form>
    );
  }

  return (
    <AuthFrame
      title="Accept invitation"
      description="Join an existing FlowPilot organization. The invitation chooses your role."
      footer={
        <Link
          className="text-foreground underline underline-offset-4"
          href={token ? loginPathForInvitation(token) : "/login"}
        >
          Back to sign in
        </Link>
      }
    >
      {body}
    </AuthFrame>
  );
}
