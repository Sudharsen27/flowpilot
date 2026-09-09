"use client";

import Link from "next/link";

import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";

export default function SettingsPage() {
  const { session, isLoading, signOut } = useAuth();

  return (
    <div className="flex max-w-lg flex-col gap-8">
      <PageHeader
        title="Settings"
        description="Identity for this browser session. Full workspace settings are not part of this phase."
      />
      {isLoading ? (
        <p className="text-muted-foreground text-sm">
          Checking signed-in state…
        </p>
      ) : session ? (
        <Card>
          <CardContent>
            <p className="text-sm font-medium">{session.user.name}</p>
            <p className="text-muted-foreground mt-1 text-sm">
              {session.user.email}
            </p>
            <p className="mt-4 text-sm">
              Organization:{" "}
              <span className="font-medium">{session.organization.name}</span>
            </p>
            <p className="text-muted-foreground text-sm">
              {session.organization.slug}
            </p>
            <Button className="mt-6" variant="outline" onClick={signOut}>
              Sign out
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="border-border bg-card max-w-lg rounded-lg border px-6 py-8">
          <h2 className="text-base font-medium tracking-tight">
            Not signed in
          </h2>
          <p className="text-muted-foreground mt-2 text-sm leading-6">
            Sign in to load the current user and organization from the API. The
            access token is stored in local storage for local development and is
            not a production session design.
          </p>
          <div className="mt-4 flex gap-3">
            <Link href="/login" className={buttonVariants()}>
              Sign in
            </Link>
            <Link
              href="/register"
              className={buttonVariants({ variant: "outline" })}
            >
              Create account
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
