import Link from "next/link";

import { Button, buttonVariants } from "@/components/ui/button";
import { buildAgentExecutionsHref } from "@/lib/agent-executions-url";
import { leadNextStep } from "@/lib/lead-next-step";
import type { Lead } from "@/types/api";

type LeadActionBarProps = {
  lead: Lead;
  canReviewDraft: boolean;
  salesRunOpen: boolean;
  onQualify: () => void;
  onDraftResponse: () => void;
  onReviewDraft: () => void;
  onFollowUps: () => void;
  onSalesAgentHistory: () => void;
};

export function LeadActionBar({
  lead,
  canReviewDraft,
  salesRunOpen,
  onQualify,
  onDraftResponse,
  onReviewDraft,
  onFollowUps,
  onSalesAgentHistory,
}: LeadActionBarProps) {
  const next = leadNextStep(lead);
  const recommended = (kind: typeof next.kind) =>
    next.kind === kind ? ("default" as const) : ("outline" as const);

  return (
    <section
      aria-labelledby="lead-actions-title"
      className="bg-card border-border grid gap-3 rounded-lg border p-4"
    >
      <div className="grid gap-1">
        <h2 id="lead-actions-title" className="text-sm font-semibold tracking-tight">
          What you can do with this lead
        </h2>
        <p className="text-muted-foreground text-xs leading-5">
          <span className="text-foreground font-medium">Suggested: {next.label}.</span>{" "}
          {next.hint}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant={recommended("analyze")} onClick={onQualify}>
          Analyze with AI
        </Button>
        <Button
          type="button"
          variant={recommended("draft-response")}
          onClick={onDraftResponse}
        >
          Draft response
        </Button>
        {canReviewDraft ? (
          <Button
            type="button"
            variant={recommended("review-draft")}
            onClick={onReviewDraft}
          >
            Review draft
          </Button>
        ) : null}
        <Button type="button" variant="outline" onClick={onFollowUps}>
          Follow-ups
        </Button>
        <Button type="button" variant="outline" onClick={onSalesAgentHistory}>
          Sales Agent history
        </Button>
        <Link
          href={buildAgentExecutionsHref({ leadId: lead.id })}
          className={buttonVariants({ variant: "outline" })}
        >
          Agent runs for this lead
        </Link>
      </div>
      <ul className="text-muted-foreground grid gap-1 text-xs leading-5">
        <li>Analyze and Draft use AI and are saved as history. Neither sends email.</li>
        <li>Email is only sent when you press Send inside an approved draft.</li>
        {salesRunOpen ? (
          <li>
            Start Sales Agent is unavailable because a Sales Agent run is already in
            progress or waiting for approval.
          </li>
        ) : null}
        {!canReviewDraft ? <li>Review draft appears once an AI draft exists.</li> : null}
      </ul>
    </section>
  );
}
