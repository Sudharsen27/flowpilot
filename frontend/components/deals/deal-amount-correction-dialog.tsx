"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
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
  correctWonDealAmount,
  forbiddenMessage,
  isRevisionConflict,
  validationErrors,
} from "@/lib/api/deals";
import { decimalEquals, formatMoney, parseAmountInput } from "@/lib/money";
import type { Deal } from "@/types/api";

type DealAmountCorrectionDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deal: Deal;
  onSaved: (deal: Deal) => void;
  /** Fetch the latest deal after a 409 conflict. */
  onReload: () => Promise<Deal | null>;
};

type Errors = Partial<Record<"amount" | "reason" | "form", string>>;

/**
 * OWNER/ADMIN only: the audited way to change a won deal's amount. The API checks the
 * role again, records the correction and its reason in the deal history, and keeps
 * the deal won in the month it was closed.
 */
export function DealAmountCorrectionDialog({
  open,
  onOpenChange,
  deal,
  onSaved,
  onReload,
}: DealAmountCorrectionDialogProps) {
  const [current, setCurrent] = useState(deal);
  const [amount, setAmount] = useState(deal.amount);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const next: Errors = {};
    const parsed = parseAmountInput(amount);
    if (!parsed.ok) next.amount = parsed.error;
    else if (decimalEquals(parsed.value, current.amount)) {
      next.amount = "Enter an amount different from the current amount.";
    }
    if (!reason.trim())
      next.reason = "Explain why the amount is being corrected.";
    setErrors(next);
    if (Object.keys(next).length > 0 || !parsed.ok) return;

    setPending(true);
    setConflict(false);
    try {
      const saved = await correctWonDealAmount(current.id, {
        expected_revision: current.revision,
        amount: parsed.value,
        reason: reason.trim(),
      });
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      if (isRevisionConflict(cause)) {
        const latest = await onReload();
        if (latest) {
          setCurrent(latest);
          setAmount(latest.amount);
        }
        setErrors({});
        setConflict(true);
      } else {
        const forbidden = forbiddenMessage(cause);
        const fields = validationErrors(cause);
        setErrors({
          amount: fields.amount,
          reason: fields.reason,
          form:
            forbidden ??
            fields.form ??
            (Object.keys(fields).length === 0
              ? "The correction could not be saved. Please try again."
              : undefined),
        });
      }
    } finally {
      setPending(false);
    }
  }

  const stillWon = current.stage === "CLOSED_WON";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Correct won amount</DialogTitle>
          <DialogDescription>
            {current.name} was won at{" "}
            {formatMoney(current.amount, current.currency)}. A correction
            replaces that amount, stays in the month the deal was won, and is
            recorded in the deal history with your reason.
          </DialogDescription>
        </DialogHeader>
        {conflict ? (
          <p
            className="border-warning/30 bg-warning/10 text-warning-text mt-4 rounded-md border px-3 py-2 text-sm"
            role="alert"
          >
            {stillWon
              ? "Someone else changed this deal, so the correction was not saved. We loaded the latest amount; review it and submit again if a correction is still needed."
              : "Someone else changed this deal and it is no longer won, so it cannot be corrected here."}
          </p>
        ) : null}
        {errors.form ? (
          <p className="text-danger-text mt-4 text-sm" role="alert">
            {errors.form}
          </p>
        ) : null}
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <FormField
            label={`Corrected amount (${current.currency})`}
            htmlFor="deal-correction-amount"
            required
            error={errors.amount}
          >
            <Input
              id="deal-correction-amount"
              inputMode="decimal"
              autoComplete="off"
              value={amount}
              disabled={!stillWon}
              aria-invalid={errors.amount ? true : undefined}
              aria-describedby={
                errors.amount ? "deal-correction-amount-error" : undefined
              }
              onChange={(event) => setAmount(event.target.value)}
              autoFocus
            />
          </FormField>
          <FormField
            label="Correction reason"
            htmlFor="deal-correction-reason"
            required
            error={errors.reason}
            description="Required. Saved in the deal history, e.g. the invoice or credit note."
          >
            <Textarea
              id="deal-correction-reason"
              value={reason}
              maxLength={1000}
              disabled={!stillWon}
              aria-invalid={errors.reason ? true : undefined}
              aria-describedby={
                errors.reason
                  ? "deal-correction-reason-error"
                  : "deal-correction-reason-description"
              }
              onChange={(event) => setReason(event.target.value)}
            />
          </FormField>
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !stillWon}>
              {pending ? "Saving…" : "Record correction"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
