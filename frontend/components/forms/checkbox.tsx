import { Check } from "lucide-react";
import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

export function Checkbox({ className, ...props }: ComponentProps<"input">) {
  return (
    <span className="relative inline-flex size-4 shrink-0">
      <input
        data-slot="checkbox"
        type="checkbox"
        className={cn(
          "border-input bg-background peer size-4 appearance-none rounded border outline-none",
          "checked:border-primary checked:bg-primary",
          "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      <Check
        aria-hidden="true"
        className="text-primary-foreground pointer-events-none absolute inset-0 hidden size-4 p-0.5 peer-checked:block"
      />
    </span>
  );
}
