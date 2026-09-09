"use client";

import type { ComponentProps } from "react";

import { cn } from "@/lib/utils";

type SwitchProps = Omit<ComponentProps<"button">, "onChange"> & {
  checked: boolean;
  onCheckedChange?: (checked: boolean) => void;
};

export function Switch({
  checked,
  onCheckedChange,
  className,
  disabled,
  ...props
}: SwitchProps) {
  return (
    <button
      data-slot="switch"
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      className={cn(
        "border-input bg-muted relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border transition-colors outline-none",
        "focus-visible:ring-ring/40 focus-visible:ring-2 focus-visible:ring-offset-2",
        "aria-checked:bg-primary disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      onClick={() => onCheckedChange?.(!checked)}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn(
          "bg-background pointer-events-none block size-4 rounded-full shadow-sm transition-transform",
          checked ? "translate-x-4" : "translate-x-0",
        )}
      />
    </button>
  );
}
