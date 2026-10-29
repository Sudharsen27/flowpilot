"use client";

import { type FormEvent, useState } from "react";

import { FormField } from "@/components/forms/form-field";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
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
import { ApiError } from "@/lib/api/client";
import { validationErrors } from "@/lib/api/deals";
import { upsertSalesTarget } from "@/lib/api/sales-targets";
import { formatMoney, formatMonth, parseAmountInput } from "@/lib/money";
import type { MemberPublic, SalesTarget, SalesTargetUpsertRequest } from "@/types/api";

const ORGANIZATION_WIDE = "__organization__";

/** First day of each month in `year`, the only period shape the API accepts. */
export function monthStarts(year: number): string[] {
  return Array.from({ length: 12 }, (_, index) => `${year}-${String(index + 1).padStart(2, "0")}-01`);
}

type SalesTargetDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  year: number;
  currency: string | null;
  members: MemberPublic[];
  targets: SalesTarget[];
  /** Prefill (and lock) the month and owner, e.g. when editing an existing target. */
  initial?: { periodStart: string; ownerUserId: string | null } | null;
  onSaved: (target: SalesTarget, created: boolean) => void;
};

type Errors = Partial<Record<"periodStart" | "owner" | "amount" | "form", string>>;

export function SalesTargetDialog({
  open,
  onOpenChange,
  year,
  currency,
  members,
  targets,
  initial,
  onSaved,
}: SalesTargetDialogProps) {
  const locked = Boolean(initial);
  const [periodStart, setPeriodStart] = useState(initial?.periodStart ?? monthStarts(year)[0]);
  const [owner, setOwner] = useState(initial?.ownerUserId ?? ORGANIZATION_WIDE);
  const ownerUserId = owner === ORGANIZATION_WIDE ? null : owner;
  const existing = targets.find(
    (target) => target.period_start === periodStart && target.owner_user_id === ownerUserId,
  );
  const [amount, setAmount] = useState(existing?.amount ?? "");
  const [errors, setErrors] = useState<Errors>({});
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const parsed = parseAmountInput(amount);
    if (!parsed.ok) {
      setErrors({ amount: parsed.error });
      return;
    }
    setErrors({});
    setPending(true);
    try {
      const payload: SalesTargetUpsertRequest = {
        period_start: periodStart,
        amount: parsed.value,
      };
      if (ownerUserId) payload.owner_user_id = ownerUserId;
      const saved = await upsertSalesTarget(payload);
      onSaved(saved, !existing);
      onOpenChange(false);
    } catch (cause) {
      const fields = validationErrors(cause);
      if (Object.keys(fields).length > 0) {
        setErrors({
          periodStart: fields.period_start ?? fields.period_end,
          owner: fields.owner_user_id,
          amount: fields.amount,
          form: fields.form,
        });
      } else if (cause instanceof ApiError && cause.status === 403) {
        setErrors({ form: "Only owners and admins can set sales targets." });
      } else {
        setErrors({ form: "The target could not be saved. Please try again." });
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{existing ? "Update sales target" : "Set sales target"}</DialogTitle>
          <DialogDescription>
            Targets cover one calendar month, either for the whole organization or for one
            owner. Each month has at most one target of each kind.
          </DialogDescription>
        </DialogHeader>
        {errors.form ? (
          <p className="text-danger-text mt-4 text-sm" role="alert">
            {errors.form}
          </p>
        ) : null}
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Month" htmlFor="target-month" error={errors.periodStart}>
              <Select
                id="target-month"
                value={periodStart}
                disabled={locked}
                onChange={(event) => {
                  setPeriodStart(event.target.value);
                  const match = targets.find(
                    (target) =>
                      target.period_start === event.target.value &&
                      target.owner_user_id === ownerUserId,
                  );
                  setAmount(match?.amount ?? "");
                }}
              >
                {monthStarts(year).map((start) => (
                  <option key={start} value={start}>
                    {formatMonth(start)}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Applies to" htmlFor="target-owner" error={errors.owner}>
              <Select
                id="target-owner"
                value={owner}
                disabled={locked}
                onChange={(event) => {
                  setOwner(event.target.value);
                  const nextOwner =
                    event.target.value === ORGANIZATION_WIDE ? null : event.target.value;
                  const match = targets.find(
                    (target) =>
                      target.period_start === periodStart && target.owner_user_id === nextOwner,
                  );
                  setAmount(match?.amount ?? "");
                }}
              >
                <option value={ORGANIZATION_WIDE}>Whole organization</option>
                {members.map((member) => (
                  <option key={member.user.id} value={member.user.id}>
                    {member.user.name}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
          {existing ? (
            <p className="bg-surface-subtle border-border rounded-md border px-3 py-2 text-sm" role="note">
              Current target: {formatMoney(existing.amount, existing.currency)}. Saving replaces it.
            </p>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <FormField label="Target amount" htmlFor="target-amount" required error={errors.amount}>
              <Input
                id="target-amount"
                inputMode="decimal"
                autoComplete="off"
                placeholder="500000.00"
                value={amount}
                aria-invalid={errors.amount ? true : undefined}
                aria-describedby={errors.amount ? "target-amount-error" : undefined}
                onChange={(event) => setAmount(event.target.value)}
                autoFocus
              />
            </FormField>
            <FormField label="Currency" htmlFor="target-currency" description="Set by your organization">
              <Input
                id="target-currency"
                aria-describedby="target-currency-description"
                value={currency ?? "—"}
                readOnly
                disabled
              />
            </FormField>
          </div>
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : existing ? "Update target" : "Set target"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
