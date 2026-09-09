"use client";

import { Button } from "@/components/ui/button";
import { StatePanel } from "@/components/data-display/state-panel";

export default function AppError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <StatePanel
      kind="error"
      title="This page could not be loaded"
      description="Try loading the page again. If the problem continues, contact your workspace administrator."
      action={<Button onClick={reset}>Try again</Button>}
    />
  );
}
