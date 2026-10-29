"use client";

import { X } from "lucide-react";
import { type FormEvent, useEffect, useId, useState } from "react";

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
import { ApiError } from "@/lib/api/client";
import {
  createDeal,
  forbiddenMessage,
  isRevisionConflict,
  updateDeal,
  validationErrors,
} from "@/lib/api/deals";
import { getLeads } from "@/lib/api/leads";
import {
  DEAL_STAGES,
  DEAL_STAGE_LABELS,
  canManageDeals,
  creatableStages,
  isClosedStage,
} from "@/lib/deals";
import { decimalEquals, parseAmountInput } from "@/lib/money";
import type {
  Deal,
  DealCreateRequest,
  DealStage,
  DealUpdateRequest,
  Lead,
  MemberPublic,
} from "@/types/api";

/** Owner select sentinels: keep the API default (the creator) or leave unassigned. */
const OWNER_SELF = "__self__";
const OWNER_NONE = "__none__";

type LeadOption = { id: string; name: string };

type DealFormDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Present when editing. */
  deal?: Deal | null;
  currency: string | null;
  members: MemberPublic[];
  currentUserId: string | undefined;
  role: string | undefined;
  initialLead?: LeadOption | null;
  onSaved: (deal: Deal) => void;
  /** Edit only: fetch the latest deal after a 409 conflict. */
  onReload?: () => Promise<Deal | null>;
};

type FormState = {
  name: string;
  description: string;
  amount: string;
  stage: DealStage;
  probability: string;
  expectedCloseDate: string;
  owner: string;
  lostReason: string;
  changeReason: string;
  lead: LeadOption | null;
};

type FieldErrors = Partial<Record<keyof FormState | "form", string>>;

function formFromDeal(deal: Deal | null | undefined, initialLead?: LeadOption | null): FormState {
  if (!deal) {
    return {
      name: "",
      description: "",
      amount: "",
      stage: "QUALIFICATION",
      probability: "",
      expectedCloseDate: "",
      owner: OWNER_SELF,
      lostReason: "",
      changeReason: "",
      lead: initialLead ?? null,
    };
  }
  return {
    name: deal.name,
    description: deal.description ?? "",
    amount: deal.amount,
    stage: deal.stage,
    probability: deal.probability === null ? "" : String(deal.probability),
    expectedCloseDate: deal.expected_close_date,
    owner: deal.owner_user_id ?? OWNER_NONE,
    lostReason: deal.lost_reason ?? "",
    changeReason: "",
    lead: deal.lead_id ? { id: deal.lead_id, name: deal.lead_name ?? "Linked lead" } : null,
  };
}

function trimmedOrNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function validate(form: FormState, isEdit: boolean): { errors: FieldErrors; amount?: string } {
  const errors: FieldErrors = {};
  if (!form.name.trim()) errors.name = "Enter a deal name.";
  const amount = parseAmountInput(form.amount);
  if (!amount.ok) errors.amount = amount.error;
  if (!form.expectedCloseDate) errors.expectedCloseDate = "Choose an expected close date.";
  if (form.probability.trim()) {
    const value = Number(form.probability);
    if (!/^\d{1,3}$/.test(form.probability.trim()) || value < 0 || value > 100) {
      errors.probability = "Enter a whole number from 0 to 100, or leave blank for the stage default.";
    }
  }
  if (form.stage === "CLOSED_LOST" && !form.lostReason.trim()) {
    errors.lostReason = "Explain why the deal was lost.";
  }
  if (!isEdit && form.stage !== "CLOSED_LOST" && form.lostReason.trim()) {
    errors.lostReason = "Only lost deals have a lost reason.";
  }
  return { errors, amount: amount.ok ? amount.value : undefined };
}

const SERVER_FIELD: Record<string, keyof FormState | "form"> = {
  name: "name",
  description: "description",
  amount: "amount",
  stage: "stage",
  probability: "probability",
  expected_close_date: "expectedCloseDate",
  owner_user_id: "owner",
  lost_reason: "lostReason",
  change_reason: "changeReason",
  lead_id: "lead",
  form: "form",
};

/**
 * The API's 403 details for owner assignment (backend deal_service.py). Matched exactly so
 * no other permission error lands on the Owner field; a reworded message falls back to
 * a form-level error.
 */
const OWNER_PERMISSION_DETAILS: ReadonlySet<string> = new Set([
  "Only owners and admins can assign deals to other members",
  "Only owners and admins can reassign deal owners",
]);

function serverErrors(cause: unknown): FieldErrors {
  const mapped: FieldErrors = {};
  for (const [field, message] of Object.entries(validationErrors(cause))) {
    mapped[SERVER_FIELD[field] ?? "form"] = message;
  }
  if (Object.keys(mapped).length > 0) return mapped;
  if (cause instanceof ApiError && cause.status === 404) {
    return { lead: "This lead no longer exists or is not in your organization." };
  }
  const forbidden = forbiddenMessage(cause);
  if (forbidden) {
    // Show the API's reason where it applies: owner assignment, or the whole form.
    return OWNER_PERMISSION_DETAILS.has(forbidden) ? { owner: forbidden } : { form: forbidden };
  }
  return { form: "The deal could not be saved. Please try again." };
}

function LeadPicker({
  value,
  onChange,
  disabled,
  error,
  describedByDescription = false,
}: {
  value: LeadOption | null;
  onChange: (lead: LeadOption | null) => void;
  disabled: boolean;
  error?: string;
  describedByDescription?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Lead[]>([]);
  const [searching, setSearching] = useState(false);
  const listId = useId();

  useEffect(() => {
    const term = query.trim();
    if (value || term.length < 2) return;
    let cancelled = false;
    const handle = window.setTimeout(() => {
      setSearching(true);
      void getLeads({ q: term, limit: 8 })
        .then((page) => {
          if (!cancelled) setResults(page.items);
        })
        .catch(() => {
          if (!cancelled) setResults([]);
        })
        .finally(() => {
          if (!cancelled) setSearching(false);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [query, value]);

  if (value) {
    return (
      <div className="border-border bg-surface-subtle flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
        <span className="truncate">{value.name}</span>
        {disabled ? null : (
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            aria-label={`Remove linked lead ${value.name}`}
            onClick={() => onChange(null)}
          >
            <X aria-hidden="true" />
          </Button>
        )}
      </div>
    );
  }

  const term = query.trim();
  return (
    <div className="grid gap-2">
      <Input
        id="deal-lead"
        type="search"
        placeholder="Search leads by name or email"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-controls={listId}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          error ? "deal-lead-error" : describedByDescription ? "deal-lead-description" : undefined
        }
        disabled={disabled}
      />
      {term.length >= 2 ? (
        <ul id={listId} aria-label="Matching leads" className="grid gap-1" aria-busy={searching}>
          {searching ? (
            <li className="text-muted-foreground text-xs" role="status">
              Searching leads…
            </li>
          ) : results.length === 0 ? (
            <li className="text-muted-foreground text-xs">No matching leads.</li>
          ) : (
            results.map((lead) => (
              <li key={lead.id}>
                <button
                  type="button"
                  onClick={() => {
                    onChange({ id: lead.id, name: lead.name });
                    setQuery("");
                    setResults([]);
                  }}
                  className="border-border hover:bg-muted/60 focus-visible:ring-ring w-full rounded-md border px-3 py-1.5 text-left text-sm outline-none focus-visible:ring-2"
                >
                  {lead.name}
                  {lead.email ? (
                    <span className="text-muted-foreground"> · {lead.email}</span>
                  ) : null}
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  );
}

export function DealFormDialog({
  open,
  onOpenChange,
  deal,
  currency,
  members,
  currentUserId,
  role,
  initialLead,
  onSaved,
  onReload,
}: DealFormDialogProps) {
  const isEdit = Boolean(deal);
  const canAssign = canManageDeals(role);
  const [form, setForm] = useState<FormState>(() => formFromDeal(deal, initialLead));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [pending, setPending] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [baseline, setBaseline] = useState<Deal | null>(deal ?? null);

  const closed = isClosedStage(form.stage);
  const lost = form.stage === "CLOSED_LOST";
  // Won amounts change only through the audited correction (OWNER/ADMIN).
  const amountLocked = baseline?.stage === "CLOSED_WON";
  const stageOptions = isEdit ? DEAL_STAGES : creatableStages(role);
  const others = members.filter((member) => member.user.id !== currentUserId);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const { errors: clientErrors, amount } = validate(form, isEdit);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0 || amount === undefined) return;
    setPending(true);
    setConflict(false);
    try {
      const saved = baseline
        ? await updateDeal(baseline.id, buildUpdate(baseline, form, amount))
        : await createDeal(buildCreate(form, amount));
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      if (baseline && isRevisionConflict(cause)) {
        const latest = onReload ? await onReload() : null;
        if (latest) {
          setBaseline(latest);
          setForm(formFromDeal(latest));
        }
        setErrors({});
        setConflict(true);
      } else {
        setErrors(serverErrors(cause));
      }
    } finally {
      setPending(false);
    }
  }

  function buildCreate(state: FormState, amount: string): DealCreateRequest {
    const payload: DealCreateRequest = {
      name: state.name.trim(),
      description: trimmedOrNull(state.description),
      amount,
      stage: state.stage,
      expected_close_date: state.expectedCloseDate,
      lead_id: state.lead?.id ?? null,
    };
    if (!isClosedStage(state.stage) && state.probability.trim()) {
      payload.probability = Number(state.probability);
    }
    if (state.stage === "CLOSED_LOST") payload.lost_reason = state.lostReason.trim();
    if (state.owner === OWNER_NONE) payload.owner_user_id = null;
    else if (state.owner !== OWNER_SELF) payload.owner_user_id = state.owner;
    return payload;
  }

  function buildUpdate(current: Deal, state: FormState, amount: string): DealUpdateRequest {
    const payload: DealUpdateRequest = { expected_revision: current.revision };
    const name = state.name.trim();
    if (name !== current.name) payload.name = name;
    const description = trimmedOrNull(state.description);
    if (description !== current.description) payload.description = description;
    if (current.stage !== "CLOSED_WON" && !decimalEquals(amount, current.amount)) {
      payload.amount = amount;
    }
    if (state.expectedCloseDate !== current.expected_close_date) {
      payload.expected_close_date = state.expectedCloseDate;
    }
    if (!isClosedStage(current.stage)) {
      const probability = state.probability.trim() ? Number(state.probability) : null;
      if (probability !== current.probability) payload.probability = probability;
    }
    const owner = state.owner === OWNER_NONE ? null : state.owner;
    if (canAssign && owner !== current.owner_user_id) payload.owner_user_id = owner;
    if (current.stage === "CLOSED_LOST") {
      const reason = state.lostReason.trim();
      if (reason !== (current.lost_reason ?? "")) payload.lost_reason = reason;
    }
    const changeReason = trimmedOrNull(state.changeReason);
    if (changeReason) payload.change_reason = changeReason;
    return payload;
  }

  /** Link the input to its error, or else to its visible help text. */
  function fieldProps(key: keyof FormState, hasDescription = false) {
    const id = `deal-${key}`;
    return {
      id,
      "aria-invalid": errors[key] ? true : undefined,
      "aria-describedby": errors[key]
        ? `${id}-error`
        : hasDescription
          ? `${id}-description`
          : undefined,
    };
  }

  const ownerLabel = (userId: string | null) =>
    members.find((member) => member.user.id === userId)?.user.name ?? "Unknown member";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit deal" : "Create deal"}</DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update deal details. Use Change stage to move the deal through the pipeline."
              : "Record a revenue opportunity. Linking a lead marks that lead as converted."}
          </DialogDescription>
        </DialogHeader>
        {conflict ? (
          <p
            className="border-warning/30 bg-warning/10 text-warning-text mt-4 rounded-md border px-3 py-2 text-sm"
            role="alert"
          >
            Someone else changed this deal. We loaded the latest version and your changes were
            not saved. Review the details and apply your changes again.
          </p>
        ) : null}
        {errors.form ? (
          <p className="text-danger-text mt-4 text-sm" role="alert">
            {errors.form}
          </p>
        ) : null}
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit} noValidate>
          <FormField label="Deal name" htmlFor="deal-name" required error={errors.name}>
            <Input
              {...fieldProps("name")}
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              maxLength={200}
              autoFocus
            />
          </FormField>
          <FormField
            label="Associated lead"
            htmlFor="deal-lead"
            error={errors.lead}
            description={
              isEdit ? "The linked lead is set when the deal is created." : undefined
            }
          >
            <LeadPicker
              value={form.lead}
              onChange={(lead) => update("lead", lead)}
              disabled={isEdit || pending}
              error={errors.lead}
              describedByDescription={isEdit}
            />
          </FormField>
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_8rem]">
            <FormField
              label="Amount"
              htmlFor="deal-amount"
              required
              error={errors.amount}
              description={
                amountLocked
                  ? canAssign
                    ? "Won amounts are locked. Use Correct amount on the deal page to record a change with a reason."
                    : "Won amounts are locked. An owner or admin can record a correction."
                  : undefined
              }
            >
              <Input
                {...fieldProps("amount", amountLocked)}
                inputMode="decimal"
                autoComplete="off"
                placeholder="125000.50"
                value={form.amount}
                readOnly={amountLocked}
                onChange={(event) => update("amount", event.target.value)}
              />
            </FormField>
            <FormField
              label="Currency"
              htmlFor="deal-currency"
              description="Set by your organization"
            >
              <Input
                id="deal-currency"
                aria-describedby="deal-currency-description"
                value={deal?.currency ?? currency ?? "—"}
                readOnly
                disabled
              />
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label="Stage"
              htmlFor="deal-stage"
              error={errors.stage}
              description={
                isEdit
                  ? "Change the stage from the deal page."
                  : canAssign
                    ? undefined
                    : "Create the deal in an open stage, then mark it won or lost when it closes."
              }
            >
              <Select
                {...fieldProps("stage", isEdit || !canAssign)}
                value={form.stage}
                disabled={isEdit}
                onChange={(event) => {
                  const stage = event.target.value as DealStage;
                  setForm((current) => ({
                    ...current,
                    stage,
                    probability: isClosedStage(stage) ? "" : current.probability,
                    lostReason: stage === "CLOSED_LOST" ? current.lostReason : "",
                  }));
                }}
              >
                {stageOptions.map((stage) => (
                  <option key={stage} value={stage}>
                    {DEAL_STAGE_LABELS[stage]}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField
              label="Probability override (%)"
              htmlFor="deal-probability"
              error={errors.probability}
              description={
                closed
                  ? "Closed deals use a fixed probability."
                  : "Leave blank to use the stage default."
              }
            >
              <Input
                {...fieldProps("probability", true)}
                inputMode="numeric"
                placeholder="Stage default"
                value={form.probability}
                disabled={closed}
                onChange={(event) => update("probability", event.target.value)}
              />
            </FormField>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label="Expected close date"
              htmlFor="deal-expectedCloseDate"
              required
              error={errors.expectedCloseDate}
            >
              <Input
                {...fieldProps("expectedCloseDate")}
                type="date"
                value={form.expectedCloseDate}
                onChange={(event) => update("expectedCloseDate", event.target.value)}
              />
            </FormField>
            <FormField
              label="Owner"
              htmlFor="deal-owner"
              error={errors.owner}
              description={
                isEdit && !canAssign ? "Only owners and admins can reassign deals." : undefined
              }
            >
              {isEdit ? (
                <Select
                  {...fieldProps("owner", !canAssign)}
                  value={form.owner}
                  disabled={!canAssign}
                  onChange={(event) => update("owner", event.target.value)}
                >
                  <option value={OWNER_NONE}>Unassigned</option>
                  {form.owner !== OWNER_NONE &&
                  !members.some((member) => member.user.id === form.owner) ? (
                    <option value={form.owner}>{deal?.owner_name ?? ownerLabel(form.owner)}</option>
                  ) : null}
                  {members.map((member) => (
                    <option key={member.user.id} value={member.user.id}>
                      {member.user.name}
                    </option>
                  ))}
                </Select>
              ) : (
                <Select
                  {...fieldProps("owner")}
                  value={form.owner}
                  onChange={(event) => update("owner", event.target.value)}
                >
                  <option value={OWNER_SELF}>Me</option>
                  <option value={OWNER_NONE}>Unassigned</option>
                  {canAssign
                    ? others.map((member) => (
                        <option key={member.user.id} value={member.user.id}>
                          {member.user.name}
                        </option>
                      ))
                    : null}
                </Select>
              )}
            </FormField>
          </div>
          {lost ? (
            <FormField
              label="Lost reason"
              htmlFor="deal-lostReason"
              required
              error={errors.lostReason}
            >
              <Textarea
                {...fieldProps("lostReason")}
                value={form.lostReason}
                maxLength={1000}
                onChange={(event) => update("lostReason", event.target.value)}
              />
            </FormField>
          ) : null}
          <FormField label="Description" htmlFor="deal-description" error={errors.description}>
            <Textarea
              {...fieldProps("description")}
              value={form.description}
              maxLength={4000}
              onChange={(event) => update("description", event.target.value)}
            />
          </FormField>
          {isEdit ? (
            <FormField
              label="Reason for change"
              htmlFor="deal-changeReason"
              description="Saved in the deal history when the amount or close date changes."
              error={errors.changeReason}
            >
              <Input
                {...fieldProps("changeReason", true)}
                value={form.changeReason}
                maxLength={1000}
                onChange={(event) => update("changeReason", event.target.value)}
              />
            </FormField>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending}>
              {pending ? "Saving…" : isEdit ? "Save changes" : "Create deal"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
