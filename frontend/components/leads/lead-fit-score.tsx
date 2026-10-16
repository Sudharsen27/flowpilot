import { StatusBadge, type StatusValue } from "@/components/ui/status-badge";
import type { LeadFitScore } from "@/types/api";

const fitLabels: Record<LeadFitScore["fit"], string> = {
  STRONG: "Strong",
  MODERATE: "Moderate",
  WEAK: "Weak",
  UNKNOWN: "Unknown",
};

const fitStatuses: Record<LeadFitScore["fit"], StatusValue> = {
  STRONG: "success",
  MODERATE: "warning",
  WEAK: "low",
  UNKNOWN: "draft",
};

const criterionLabels: Record<string, string> = {
  company: "Company",
  enquiry: "Enquiry",
};

const unavailableLabels: Record<string, string> = {
  industry: "Industry",
  employee_range: "Company size",
  geographic_region: "Region",
  buyer_role: "Buyer role",
};

export function LeadFitScorePanel({
  score,
}: {
  score: LeadFitScore | null | undefined;
}) {
  const fit = score?.fit ?? "UNKNOWN";

  return (
    <section
      className="border-border grid gap-3 border-t pt-4"
      aria-labelledby="lead-fit-score-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id="lead-fit-score-title" className="text-sm font-medium">
          Prospect fit
        </h3>
        <StatusBadge
          status={fitStatuses[fit]}
          label={
            score?.score === null || score?.score === undefined
              ? "Unknown"
              : `${fitLabels[fit]} · ${score.score}/100`
          }
        />
      </div>
      <p className="text-muted-foreground text-xs">
        Assessment confidence: {score?.confidence ?? 0}%
      </p>
      {score?.configuration_valid === false ? (
        <p className="text-danger-text text-sm">
          The saved profile is invalid. An owner or admin must correct it.
        </p>
      ) : null}
      <ul className="grid gap-2">
        {(score?.components ?? []).map((component) => (
          <li key={component.criterion} className="grid gap-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">
                {criterionLabels[component.criterion]}
              </span>
              <StatusBadge
                status={
                  component.status === "MATCHED"
                    ? "success"
                    : component.status === "UNMATCHED"
                      ? "warning"
                      : "draft"
                }
                label={
                  component.status === "UNCONFIGURED"
                    ? "Not configured"
                    : component.status.charAt(0) +
                      component.status.slice(1).toLowerCase()
                }
              />
            </div>
            <p className="text-muted-foreground text-xs leading-5">
              {component.explanation}
            </p>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground text-xs leading-5">
        Not assessed:{" "}
        {Object.keys(score?.unavailable_criteria ?? unavailableLabels)
          .map((criterion) => unavailableLabels[criterion] ?? criterion)
          .join(", ")}
        .
      </p>
    </section>
  );
}
