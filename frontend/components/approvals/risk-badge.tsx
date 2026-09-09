import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type RiskLevel = "low" | "medium" | "high";

type RiskBadgeProps = {
  level: RiskLevel;
};

const riskPresentation: Record<
  RiskLevel,
  { status: StatusValue; label: string }
> = {
  low: { status: "low", label: "Low risk" },
  medium: { status: "medium", label: "Medium risk" },
  high: { status: "high", label: "High risk" },
};

export function RiskBadge({ level }: RiskBadgeProps) {
  const presentation = riskPresentation[level];
  return (
    <StatusBadge status={presentation.status} label={presentation.label} />
  );
}
