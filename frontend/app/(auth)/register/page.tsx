"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AuthFrame } from "@/components/auth/auth-frame";
import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";

export default function RegisterPage() {
  const router = useRouter();
  const { signUp } = useAuth();
  const [name, setName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await signUp({ email, password, name, organizationName });
      router.push("/");
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 409
          ? "That email is already registered."
          : "Unable to create the account.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <AuthFrame
      title="Create account"
      description="This creates your user, your organization, and an owner membership. You approve customer messages before they are sent."
      footer={
        <>
          Already registered?{" "}
          <Link className="text-foreground underline underline-offset-4" href="/login">
            Sign in
          </Link>
        </>
      }
    >
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <FormField label="Your name" htmlFor="name" required>
          <Input
            id="name"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </FormField>
        <FormField
          label="Organization name"
          htmlFor="organization-name"
          required
        >
          <Input
            id="organization-name"
            autoComplete="organization"
            value={organizationName}
            onChange={(event) => setOrganizationName(event.target.value)}
            required
          />
        </FormField>
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
        <FormField
          label="Password"
          htmlFor="password"
          description="Use at least 8 characters."
          required
        >
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            minLength={8}
            aria-describedby="password-description"
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
          {pending ? "Creating…" : "Create account"}
        </Button>
      </form>
    </AuthFrame>
  );
}
