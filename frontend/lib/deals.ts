import { statusPresentation } from "@/lib/status";
import type { StatusValue } from "@/components/ui/status-badge";
import type { DealStage } from "@/types/api";

/** Pipeline order. Win probabilities come from the API, never from this file. */
export const DEAL_STAGES: readonly DealStage[] = [
  "QUALIFICATION",
  "DISCOVERY",
  "PROPOSAL",
  "NEGOTIATION",
  "CLOSED_WON",
  "CLOSED_LOST",
];

export const DEAL_STAGE_LABELS: Record<DealStage, string> = {
  QUALIFICATION: "Qualification",
  DISCOVERY: "Discovery",
  PROPOSAL: "Proposal",
  NEGOTIATION: "Negotiation",
  CLOSED_WON: "Closed won",
  CLOSED_LOST: "Closed lost",
};

export const CLOSED_DEAL_STAGES: ReadonlySet<DealStage> = new Set(["CLOSED_WON", "CLOSED_LOST"]);

export function isClosedStage(stage: DealStage): boolean {
  return CLOSED_DEAL_STAGES.has(stage);
}

export function isDealStage(value: string): value is DealStage {
  return (DEAL_STAGES as readonly string[]).includes(value);
}

const STAGE_SEMANTICS: Record<DealStage, StatusValue> = {
  QUALIFICATION: "draft",
  DISCOVERY: "pending",
  PROPOSAL: "pending",
  NEGOTIATION: "warning",
  CLOSED_WON: "success",
  CLOSED_LOST: "failed",
};

export function dealStagePresentation(stage: DealStage) {
  return statusPresentation(stage, DEAL_STAGE_LABELS[stage], STAGE_SEMANTICS[stage]);
}

export function canManageDeals(role: string | undefined): boolean {
  return role === "OWNER" || role === "ADMIN";
}
