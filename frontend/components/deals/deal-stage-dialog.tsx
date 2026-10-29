"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  changeDealStage,
  forbiddenMessage,
  isRevisionConflict,
  validationErrors,
} from "@/lib/api/deals";
import {
  DEAL_STAGES,
  DEAL_STAGE_LABELS,
  WON_STAGE_LOCKED_MESSAGE,
  canChangeStage,
  isClosedStage,
} from "@/lib/deals";
import type { Deal, DealStage } from "@/types/api";

type DealStageDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deal: Deal;
  onSaved: (deal: Deal) => void;
  /** Fetch the latest deal after a 409 conflict. */
  onReload: () => Promise<Deal | null>;
  /** Preselect the target stage, e.g. after dropping a card on a closed column. */
  initialStage?: DealStage;
  /** The viewer's membership role; leaving CLOSED_WON is manager-only. */
  role: string | undefined;
};

type Errors = Partial<Record<"stage" | "probability" | "lostReason" | "form", string>>;

export function DealStageDialog({
  open,
  onOpenChange,
  deal,
  onSaved,
  onReload,
  initialStage,
  role,
}: DealStageDialogProps) {
  const [current, setCurrent] = useState(deal);
  const [stage, setStage] = useState<DealStage | "">(
    initialStage && initialStage !== deal.stage ? initialStage : "",
  );
  const [probability, setProbability] = useState("");
  const [lostReason, setLostReason] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);

  const locked = !canChangeStage(current, role);
  const closing = stage !== "" && isClosedStage(stage);
  const reopening = stage !== "" && !closing && isClosedStage(current.stage);
  const submitLabel =
    stage === "CLOSED_WON"
      ? "Mark as won"
      : stage === "CLOSED_LOST"
        ? "Mark as lost"
        : stage
          ? `Move to ${DEAL_STAGE_LABELS[stage]}`
          : "Change stage";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const next: Errors = {};
    if (!stage) next.stage = "Choose a new stage.";
    if (stage && !closing && probability.trim()) {
      const value = Number(probability);
      if (!/^\d{1,3}$/.test(probability.trim()) || value > 100) {
        next.probability = "Enter a whole number from 0 to 100, or leave blank.";
      }
    }
    if (stage === "CLOSED_LOST" && !lostReason.trim()) {
      next.lostReason = "Explain why the deal was lost.";
    }
    setErrors(next);
    if (Object.keys(next).length > 0 || !stage) return;

    setPending(true);
    setConflict(false);
    try {
      const saved = await changeDealStage(current.id, {
        stage,
        expected_revision: current.revision,
        probability: !closing && probability.trim() ? Number(probability) : null,
        lost_reason: stage === "CLOSED_LOST" ? lostReason.trim() : null,
        change_reason: changeReason.trim() || null,
      });
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      if (isRevisionConflict(cause)) {
        const latest = await onReload();
        if (latest) setCurrent(latest);
        setStage("");
        setErrors({});
        setConflict(true);
      } else {
        const forbidden = forbiddenMessage(cause);
        const fields = validationErrors(cause);
        setErrors({
          stage: fields.stage,
          probability: fields.probability,
          lostReason: fields.lost_reason,
          form:
            forbidden ??
            fields.form ??
            (Object.keys(fields).length === 0
              ? "The stage could not be changed. Please try again."
              : undefined),
        });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Change stage</DialogTitle>
          <DialogDescription>
            {current.name} is in {DEAL_STAGE_LABELS[current.stage]}. Every stage change is
            recorded in the deal history.
          </DialogDescription>
        </DialogHeader>
        {conflict ? (
          <p
            className="border-warning/30 bg-warning/10 text-warning-text mt-4 rounded-md border px-3 py-2 text-sm"
            role="alert"
          >
            Someone else changed this deal, so the stage was not changed. We loaded the latest
            version; choose the stage again if it is still needed.
          </p>
        ) : null}
        {errors.form ? (
          <p className="text-danger-text mt-4 text-sm" role="alert">
            {errors.form}
          </p>
        ) : null}
        {locked ? (
          <>
            <p
              className="border-border bg-surface-subtle mt-6 rounded-md border px-3 py-2 text-sm"
              role="note"
            >
              {WON_STAGE_LOCKED_MESSAGE}
            </p>
            <DialogFooter>
              <DialogCancel>Close</DialogCancel>
            </DialogFooter>
          </>
        ) : (
          <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
            <FormField label="New stage" htmlFor="deal-new-stage" required error={errors.stage}>
              <Select
                id="deal-new-stage"
                value={stage}
                aria-invalid={errors.stage ? true : undefined}
                aria-describedby={errors.stage ? "deal-new-stage-error" : undefined}
                onChange={(event) => {
                  const value = event.target.value as DealStage | "";
                  setStage(value);
                  if (value === "" || isClosedStage(value)) setProbability("");
                  if (value !== "CLOSED_LOST") setLostReason("");
                }}
              >
                <option value="">Choose a stage</option>
                {DEAL_STAGES.filter((value) => value !== current.stage).map((value) => (
                  <option key={value} value={value}>
                    {DEAL_STAGE_LABELS[value]}
                  </option>
                ))}
              </Select>
            </FormField>

            {closing ? (
              <p
                className="border-border bg-surface-subtle rounded-md border px-3 py-2 text-sm"
                role="note"
              >
                {stage === "CLOSED_WON"
                  ? "Marking this deal as won closes it and records today as the close date. Closed deals use a fixed probability. Only owners and admins can reopen or change a won deal or correct its amount."
                  : "Marking this deal as lost closes it and records today as the close date. Closed deals use a fixed probability. You can reopen it later by moving it to an open stage."}
              </p>
            ) : null}
            {reopening ? (
              <p className="text-muted-foreground text-sm" role="note">
                Reopening clears the close date
                {current.stage === "CLOSED_LOST" ? " and the lost reason" : ""}.
              </p>
            ) : null}

            {stage && !closing ? (
              <FormField
                label="Probability override (%)"
                htmlFor="deal-stage-probability"
                error={errors.probability}
                description="Optional. Any existing override is cleared on a stage change; leave blank to use the new stage's default."
              >
                <Input
                  id="deal-stage-probability"
                  inputMode="numeric"
                  placeholder="Stage default"
                  value={probability}
                  aria-invalid={errors.probability ? true : undefined}
                  aria-describedby={
                    errors.probability
                      ? "deal-stage-probability-error"
                      : "deal-stage-probability-description"
                  }
                  onChange={(event) => setProbability(event.target.value)}
                />
              </FormField>
            ) : null}

            {stage === "CLOSED_LOST" ? (
              <FormField
                label="Lost reason"
                htmlFor="deal-stage-lost-reason"
                required
                error={errors.lostReason}
              >
                <Textarea
                  id="deal-stage-lost-reason"
                  value={lostReason}
                  maxLength={1000}
                  aria-invalid={errors.lostReason ? true : undefined}
                  aria-describedby={errors.lostReason ? "deal-stage-lost-reason-error" : undefined}
                  onChange={(event) => setLostReason(event.target.value)}
                />
              </FormField>
            ) : null}

            <FormField
              label="Reason for change"
              htmlFor="deal-stage-change-reason"
              description="Optional note saved in the deal history."
            >
              <Input
                id="deal-stage-change-reason"
                aria-describedby="deal-stage-change-reason-description"
                value={changeReason}
                maxLength={1000}
                onChange={(event) => setChangeReason(event.target.value)}
              />
            </FormField>

            <DialogFooter>
              <DialogCancel>Cancel</DialogCancel>
              <Button
                type="submit"
                disabled={pending}
                variant={stage === "CLOSED_LOST" ? "destructive" : "default"}
              >
                {pending ? "Saving…" : submitLabel}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
