import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Input({ className, type, ...props }: ComponentProps<"input">) {
  return (
    <input
      data-slot="input"
      type={type}
      className={cn(
        "border-input bg-background text-foreground placeholder:text-muted-foreground shadow-card h-9 w-full rounded-md border px-3 text-sm transition-colors outline-none",
        "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className,
      )}
      {...props}
    />
  );
}
