import type {
  WorkflowAction,
  WorkflowRule,
  WorkflowRunStatus,
  WorkflowTrigger,
} from "@/types/api";

export const workflowTriggerLabels: Record<WorkflowTrigger, string> = {
  LEAD_CREATED: "A new lead is added",
  INBOUND_REPLY_RECEIVED: "A customer replies by email",
  HUMAN_ATTENTION_REQUIRED: "The AI flags a lead for human attention",
};

export const workflowActionLabels: Record<WorkflowAction, string> = {
  ANALYZE_LEAD: "Analyze the lead with AI",
  DRAFT_RESPONSE: "Draft a reply for review",
  CREATE_FOLLOW_UP: "Schedule a follow-up reminder",
};

export const workflowActionHints: Record<WorkflowAction, string> = {
  ANALYZE_LEAD: "Scores intent and fit, and records the result on the lead.",
  DRAFT_RESPONSE:
    "Writes a reply that waits in Approvals. It is never sent automatically.",
  CREATE_FOLLOW_UP:
    "Adds a reminder to the lead so someone on your team follows up.",
};

export const allowedWorkflowActions: Record<
  WorkflowTrigger,
  readonly WorkflowAction[]
> = {
  LEAD_CREATED: ["ANALYZE_LEAD", "DRAFT_RESPONSE", "CREATE_FOLLOW_UP"],
  INBOUND_REPLY_RECEIVED: [
    "ANALYZE_LEAD",
    "DRAFT_RESPONSE",
    "CREATE_FOLLOW_UP",
  ],
  HUMAN_ATTENTION_REQUIRED: ["CREATE_FOLLOW_UP"],
};

export const workflowRunStatusLabels: Record<WorkflowRunStatus, string> = {
  PENDING: "Waiting",
  RUNNING: "Running",
  SUCCEEDED: "Done",
  SKIPPED: "Skipped",
  FAILED: "Failed",
};

export const workflowRunStatusBadge = {
  PENDING: "pending",
  RUNNING: "pending",
  SUCCEEDED: "success",
  SKIPPED: "draft",
  FAILED: "failed",
} as const satisfies Record<WorkflowRunStatus, string>;

export function describeWorkflow(
  rule: Pick<WorkflowRule, "action" | "follow_up_delay_hours">,
) {
  if (rule.action === "CREATE_FOLLOW_UP" && rule.follow_up_delay_hours) {
    const hours = rule.follow_up_delay_hours;
    const when =
      hours % 24 === 0
        ? `${hours / 24} day${hours === 24 ? "" : "s"}`
        : `${hours} hour${hours === 1 ? "" : "s"}`;
    return `Schedule a follow-up reminder due in ${when}`;
  }
  return workflowActionLabels[rule.action];
}
