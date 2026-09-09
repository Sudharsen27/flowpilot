"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

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
    <main className="mx-auto flex min-h-full max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Create account</h1>
      <p className="text-muted-foreground mt-2 text-sm">
        This creates your user, organization, and owner membership. It is a
        development sign-up form, not a finished onboarding flow.
      </p>
      <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit}>
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
        <Button type="submit" disabled={pending}>
          {pending ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="text-muted-foreground mt-6 text-sm">
        Already registered?{" "}
        <Link className="text-foreground underline" href="/login">
          Sign in
        </Link>
      </p>
    </main>
  );
}
