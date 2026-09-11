import { Bot } from "lucide-react";

import { cn } from "@/lib/utils";

export const AI_BADGE_LABELS = [
  "Generated",
  "Suggested",
  "Analysis",
  "Processing",
  "Agent",
] as const;

export type AiBadgeLabel = (typeof AI_BADGE_LABELS)[number];

type AiBadgeProps = {
  label: AiBadgeLabel;
  className?: string;
};

export function AiBadge({ label, className }: AiBadgeProps) {
  const processing = label === "Processing";

  return (
    <span
      data-slot="ai-badge"
      data-ai-label={label}
      aria-busy={processing || undefined}
      aria-label={`AI ${label}`}
      className={cn(
        "border-ai-border bg-ai/10 text-ai-text inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        className,
      )}
    >
      <Bot className="size-3.5" aria-hidden="true" />
      {label}
    </span>
  );
}
