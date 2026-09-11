import { AiBadge } from "@/components/ai/ai-badge";
import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import { statusPresentation } from "@/lib/status";
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
  { code: string; label: string; fallback?: StatusValue }
> = {
  "not-assessed": { code: "DRAFT", label: "Not assessed" },
  failed: { code: "FAILED", label: "Analysis failed" },
  QUALIFIED: { code: "QUALIFIED", label: "Qualified" },
  UNQUALIFIED: { code: "UNQUALIFIED", label: "Unqualified", fallback: "warning" },
  NEEDS_MORE_INFORMATION: {
    code: "NEEDS_MORE_INFORMATION",
    label: "Needs more information",
    fallback: "pending",
  },
};

export function QualificationStatus({
  status,
  explanation,
}: QualificationStatusProps) {
  const item = qualificationPresentation[status];
  const presentation = statusPresentation(
    item.code,
    item.label,
    item.fallback ?? "draft",
  );

  return (
    <div className="grid justify-items-start gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        {status !== "not-assessed" ? <AiBadge label="Analysis" /> : null}
        <StatusBadge status={presentation.status} label={presentation.label} />
      </div>
      {explanation ? (
        <p className="text-muted-foreground max-w-64 text-xs leading-5">
          {explanation}
        </p>
      ) : null}
    </div>
  );
}
