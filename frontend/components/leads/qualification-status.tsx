import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";

export type QualificationState =
  "not-assessed" | "pending" | "qualified" | "unqualified" | "unavailable";

type QualificationStatusProps = {
  status: QualificationState;
  score?: number;
  explanation?: string;
};

const qualificationPresentation: Record<
  QualificationState,
  { status: StatusValue; label: string }
> = {
  "not-assessed": { status: "draft", label: "Not assessed" },
  pending: { status: "pending", label: "Pending" },
  qualified: { status: "success", label: "Qualified" },
  unqualified: { status: "warning", label: "Unqualified" },
  unavailable: { status: "draft", label: "Unavailable" },
};

export function QualificationStatus({
  status,
  score,
  explanation,
}: QualificationStatusProps) {
  const presentation = qualificationPresentation[status];
  const hasValidScore =
    score !== undefined && Number.isFinite(score) && score >= 0 && score <= 100;

  return (
    <div className="grid justify-items-start gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={presentation.status} label={presentation.label} />
        {hasValidScore ? (
          <span
            className="text-muted-foreground text-xs tabular-nums"
            aria-label={`AI qualification score: ${score} out of 100`}
          >
            {score}/100
          </span>
        ) : null}
      </div>
      {explanation ? (
        <p className="text-muted-foreground max-w-64 text-xs leading-5">
          {explanation}
        </p>
      ) : null}
    </div>
  );
}
