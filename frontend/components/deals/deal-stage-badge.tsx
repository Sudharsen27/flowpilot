import { StatusBadge } from "@/components/ui/status-badge";
import { dealStagePresentation } from "@/lib/deals";
import type { Deal, DealStage } from "@/types/api";

export function DealStageBadge({ stage }: { stage: DealStage }) {
  const presentation = dealStagePresentation(stage);
  return <StatusBadge status={presentation.status} label={presentation.label} />;
}

/** "75%" plus whether it is the stage default or an override, from the API. */
export function DealProbability({
  deal,
}: {
  deal: Pick<Deal, "effective_probability" | "probability_source">;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 tabular-nums">
      <span>{deal.effective_probability}%</span>
      <span className="text-muted-foreground text-xs">
        {deal.probability_source === "OVERRIDE" ? "override" : "stage default"}
      </span>
    </span>
  );
}
