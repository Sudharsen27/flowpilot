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

export const OPEN_DEAL_STAGES: readonly DealStage[] = DEAL_STAGES.filter(
  (stage) => !CLOSED_DEAL_STAGES.has(stage),
);

/**
 * Stages a role may create a deal in, mirroring the API: members create open deals
 * and close them later through a stage change. The API remains the authority.
 */
export function creatableStages(role: string | undefined): readonly DealStage[] {
  return canManageDeals(role) ? DEAL_STAGES : OPEN_DEAL_STAGES;
}

/**
 * Whether this role may move the deal to another stage. Leaving CLOSED_WON (reopening
 * or marking lost) is manager-only in the API; every other move is open to all roles.
 */
export function canChangeStage(deal: { stage: DealStage }, role: string | undefined): boolean {
  return deal.stage !== "CLOSED_WON" || canManageDeals(role);
}

/** OWNER/ADMIN record an audited correction; nobody edits a won amount directly. */
export function canCorrectWonAmount(deal: { stage: DealStage }, role: string | undefined): boolean {
  return deal.stage === "CLOSED_WON" && canManageDeals(role);
}

export const WON_STAGE_LOCKED_MESSAGE =
  "Only owners and admins can reopen or change a won deal.";
