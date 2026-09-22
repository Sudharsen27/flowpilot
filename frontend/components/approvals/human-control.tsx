import { ShieldCheck } from "lucide-react";

import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export type ApprovalDecisionState =
  | "idle"
  | "pending"
  | "approved"
  | "sent"
  | "rejected";

type HumanControlProps = {
  decision?: ApprovalDecisionState;
};

const copy: Record<
  ApprovalDecisionState,
  { title: string; description: string; tone: "neutral" | "warning" | "success" | "danger" }
> = {
  idle: {
    title: "Human decision required",
    description:
      "Select a response to review. Approving never sends email — sending is a separate action.",
    tone: "neutral",
  },
  pending: {
    title: "Human decision required",
    description: "Review the AI response before sending.",
    tone: "warning",
  },
  approved: {
    title: "Approved by human review",
    description: "Ready to send.",
    tone: "success",
  },
  sent: {
    title: "Response sent",
    description: "This approved response was sent to the customer.",
    tone: "success",
  },
  rejected: {
    title: "Response rejected",
    description: "This response will not be sent.",
    tone: "danger",
  },
};

const toneClass: Record<ApprovalDecisionState, string> = {
  idle: "bg-muted text-muted-foreground",
  pending: "bg-warning/10 text-warning-text",
  approved: "bg-success/10 text-success-text",
  sent: "bg-success/10 text-success-text",
  rejected: "bg-destructive/10 text-danger-text",
};

export function HumanControl({ decision = "idle" }: HumanControlProps) {
  const content = copy[decision];

  return (
    <Card
      as="section"
      className="grid gap-5 p-5 sm:items-center sm:p-6"
      aria-labelledby="human-control-title"
      data-decision={decision}
    >
      <div className="flex items-start gap-3">
        <div
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-lg",
            toneClass[decision],
          )}
          aria-hidden="true"
        >
          <ShieldCheck className="size-4" />
        </div>
        <div>
          <h3 id="human-control-title" className="text-sm font-medium">
            {content.title}
          </h3>
          <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-6">
            {content.description}
          </p>
        </div>
      </div>
    </Card>
  );
}
