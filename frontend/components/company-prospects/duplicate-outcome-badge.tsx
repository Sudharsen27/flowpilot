import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import type { DuplicateAssessmentOutcome } from "@/types/api";

const outcomeAppearance: Record<
  DuplicateAssessmentOutcome,
  { status: StatusValue; label: string }
> = {
  EXACT_MATCH: { status: "failed", label: "Exact duplicate found" },
  POSSIBLE_DUPLICATE: { status: "warning", label: "Possible duplicate" },
  NEW: { status: "active", label: "No match found" },
  INSUFFICIENT_DATA: { status: "draft", label: "Insufficient data" },
};

export function DuplicateOutcomeBadge({
  outcome,
}: {
  outcome: DuplicateAssessmentOutcome;
}) {
  const appearance =
    outcomeAppearance[outcome] ?? outcomeAppearance.INSUFFICIENT_DATA;
  return <StatusBadge status={appearance.status} label={appearance.label} />;
}
