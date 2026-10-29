import { CircleCheck, CircleSlash, SignalHigh, SignalLow, SignalMedium } from "lucide-react";

import { forecastCategoryLabel } from "@/lib/deals";
import { cn } from "@/lib/utils";
import type { DealStage, ForecastCategory } from "@/types/api";

/**
 * Forecast category, styled apart from the coloured stage badge: a neutral outline with
 * a signal icon for confidence, so the two are never read as the same thing.
 */
const ICONS = {
  PIPELINE: SignalLow,
  BEST_CASE: SignalMedium,
  COMMIT: SignalHigh,
} as const;

export function ForecastCategoryBadge({
  stage,
  category,
  className,
}: {
  stage: DealStage;
  category: ForecastCategory | null | undefined;
  className?: string;
}) {
  const Icon =
    stage === "CLOSED_WON"
      ? CircleCheck
      : stage === "CLOSED_LOST"
        ? CircleSlash
        : category
          ? ICONS[category]
          : null;
  return (
    <span
      data-slot="forecast-category-badge"
      data-category={stage === "CLOSED_WON" ? "CLOSED" : (category ?? "NONE")}
      className={cn(
        "border-border text-foreground inline-flex min-h-6 items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        stage === "CLOSED_LOST" && "text-muted-foreground",
        className,
      )}
    >
      {Icon ? <Icon className="text-muted-foreground size-3.5" aria-hidden="true" /> : null}
      {forecastCategoryLabel(stage, category)}
    </span>
  );
}
