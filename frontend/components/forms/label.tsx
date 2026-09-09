import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Label({ className, ...props }: ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "text-foreground text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
