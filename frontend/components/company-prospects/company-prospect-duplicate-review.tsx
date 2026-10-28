"use client";

import { LoaderCircle } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { DuplicateOutcomeBadge } from "@/components/company-prospects/duplicate-outcome-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import {
  getCompanyProspect,
  getCompanyProspectDuplicateAssessment,
} from "@/lib/api/company-prospects";
import type { CompanyDuplicateAssessmentItem } from "@/types/api";

const FALLBACK_MATCH_NAME = "Matched prospect";

const fieldLabels: Record<string, string> = {
  company_name: "Company name",
  website_domain: "Website domain",
  cin: "CIN",
};

type MatchedProspect = { id: string; name: string | null };

type ReviewState =
  | { kind: "loading" }
  | { kind: "error" }
  | {
      kind: "loaded";
      assessment: CompanyDuplicateAssessmentItem | null;
      matches: MatchedProspect[];
    };

async function loadReview(prospectId: string) {
  const response = await getCompanyProspectDuplicateAssessment(prospectId);
  const assessment = response.assessments[0] ?? null;
  // The backend excludes the target; filter again so the page never links to itself.
  const matchIds = (assessment?.existing_match_references ?? []).filter(
    (id) => id !== prospectId,
  );
  const lookups = await Promise.allSettled(
    matchIds.map((id) => getCompanyProspect(id)),
  );
  const matches = matchIds.map((id, index) => {
    const lookup = lookups[index];
    return {
      id,
      name: lookup.status === "fulfilled" ? lookup.value.name : null,
    };
  });
  return { assessment, matches };
}

export function CompanyProspectDuplicateReview({
  prospectId,
}: {
  prospectId: string;
}) {
  const [state, setState] = useState<ReviewState>({ kind: "loading" });
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void loadReview(prospectId)
      .then(({ assessment, matches }) => {
        if (!cancelled) setState({ kind: "loaded", assessment, matches });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [prospectId, retryKey]);

  function retry() {
    setState({ kind: "loading" });
    setRetryKey((value) => value + 1);
  }

  return (
    <section
      className="border-border grid gap-5 rounded-lg border p-4 sm:p-5"
      aria-labelledby="duplicate-review-title"
    >
      <div>
        <h2 id="duplicate-review-title" className="text-section-title font-semibold tracking-tight">
          Duplicate review
        </h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Compares this record with other company prospects in your organization. Read only.
        </p>
      </div>
      <DuplicateReviewBody state={state} onRetry={retry} />
    </section>
  );
}

function DuplicateReviewBody({
  state,
  onRetry,
}: {
  state: ReviewState;
  onRetry: () => void;
}) {
  if (state.kind === "loading") {
    return (
      <div
        className="text-muted-foreground flex items-center gap-2 text-sm"
        aria-busy="true"
      >
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        <span>Checking for duplicate company prospects…</span>
      </div>
    );
  }

  if (state.kind === "error") {
    return (
      <StatePanel
        kind="error"
        headingLevel={3}
        className="max-w-none"
        title="Duplicate review unavailable"
        description="The duplicate assessment could not be loaded. Company details above are unaffected."
        action={
          <Button type="button" variant="outline" onClick={onRetry}>
            Retry duplicate review
          </Button>
        }
      />
    );
  }

  const { assessment, matches } = state;
  if (!assessment) {
    return (
      <StatePanel
        kind="information"
        headingLevel={3}
        className="max-w-none"
        title="No duplicate assessment available"
        description="No assessment was returned for this company prospect."
      />
    );
  }

  return (
    <div className="grid gap-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-muted-foreground">Outcome</span>
        <DuplicateOutcomeBadge outcome={assessment.outcome} />
      </div>
      <p className="text-muted-foreground">{assessment.explanation}</p>
      {assessment.matching_fields.length > 0 ? (
        <p className="text-muted-foreground">
          Matched fields:{" "}
          {assessment.matching_fields
            .map((field) => fieldLabels[field] ?? field)
            .join(", ")}
        </p>
      ) : null}
      {matches.length > 0 ? (
        <div className="grid gap-2">
          <h3 id="matched-prospects-title" className="font-medium">
            Matched company prospects
          </h3>
          <ul className="grid gap-1" aria-labelledby="matched-prospects-title">
            {matches.map((match) => (
              <li key={match.id}>
                <Link
                  href={`/company-prospects/${encodeURIComponent(match.id)}`}
                  className="text-primary underline-offset-4 hover:underline"
                >
                  {match.name ?? FALLBACK_MATCH_NAME}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-muted-foreground">
          No other company prospects in your organization match this record.
        </p>
      )}
    </div>
  );
}
