import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

/**
 * Joins metric cards into one bordered strip with hairline dividers.
 * Pass the column layout through `className`, e.g. `sm:grid-cols-2 xl:grid-cols-4`.
 */
export function MetricStrip({ className, ...props }: ComponentProps<"div">) {
  return (
    <div
      data-slot="metric-strip"
      className={cn(
        "border-border bg-border shadow-card grid gap-px overflow-hidden rounded-lg border",
        "[&>[data-slot=card]]:rounded-none [&>[data-slot=card]]:border-0 [&>[data-slot=card]]:shadow-none",
        className,
      )}
      {...props}
    />
  );
}
