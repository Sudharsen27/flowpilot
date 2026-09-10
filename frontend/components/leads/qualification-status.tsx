import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import type { LeadAiQualification } from "@/types/api";

export type QualificationState =
  | "not-assessed"
  | "failed"
  | LeadAiQualification;

type QualificationStatusProps = {
  status: QualificationState;
  explanation?: string;
};

const qualificationPresentation: Record<
  QualificationState,
  { status: StatusValue; label: string }
> = {
  "not-assessed": { status: "draft", label: "Not assessed" },
  failed: { status: "failed", label: "Analysis failed" },
  QUALIFIED: { status: "success", label: "AI: Qualified" },
  UNQUALIFIED: { status: "warning", label: "AI: Unqualified" },
  NEEDS_MORE_INFORMATION: { status: "pending", label: "AI: Needs more information" },
};

export function QualificationStatus({
  status,
  explanation,
}: QualificationStatusProps) {
  const presentation = qualificationPresentation[status];

  return (
    <div className="grid justify-items-start gap-1.5">
      <StatusBadge status={presentation.status} label={presentation.label} />
      {explanation ? (
        <p className="text-muted-foreground max-w-64 text-xs leading-5">
          {explanation}
        </p>
      ) : null}
    </div>
  );
}
