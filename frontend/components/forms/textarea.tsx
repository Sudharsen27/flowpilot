import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "border-input bg-background text-foreground placeholder:text-muted-foreground shadow-card min-h-24 w-full resize-y rounded-md border px-3 py-2 text-sm transition-colors outline-none",
        "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className,
      )}
      {...props}
    />
  );
}
