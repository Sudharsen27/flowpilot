"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";

export default function LoginPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await signIn(email, password);
      router.push("/");
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? "Invalid email or password."
          : "Unable to sign in.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-full max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
      <p className="text-muted-foreground mt-2 text-sm">
        Use the account created for your organization. Tokens are stored in this
        browser only.
      </p>
      <form className="mt-8 flex flex-col gap-4" onSubmit={handleSubmit}>
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
        <Button type="submit" disabled={pending}>
          {pending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="text-muted-foreground mt-6 text-sm">
        Need an organization?{" "}
        <Link className="text-foreground underline" href="/register">
          Create an account
        </Link>
      </p>
    </main>
  );
}
