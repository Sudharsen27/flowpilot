"use client";

import { Button } from "@/components/ui/button";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="border-border bg-card max-w-lg rounded-lg border px-6 py-8">
      <h1 className="text-lg font-semibold tracking-tight">
        This page could not be loaded
      </h1>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        Try loading the page again. If the problem continues, contact your
        workspace administrator.
      </p>
      <Button className="mt-5" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
