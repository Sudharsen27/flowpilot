"use client";

import { type FormEvent, useState } from "react";

import { leadSourceLabels } from "@/components/analytics/analytics-toolbar";
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
import {
  allowedWorkflowActions,
  workflowActionHints,
  workflowActionLabels,
  workflowTriggerLabels,
} from "@/components/workflows/workflow-labels";
import { ApiError } from "@/lib/api/client";
import { createWorkflow, updateWorkflow } from "@/lib/api/workflows";
import type {
  LeadSource,
  WorkflowAction,
  WorkflowRule,
  WorkflowTrigger,
} from "@/types/api";

const DELAY_OPTIONS = [1, 4, 24, 48, 72, 168] as const;

function delayLabel(hours: number) {
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"}`;
  const days = hours / 24;
  return days === 7 ? "1 week" : `${days} day${days === 1 ? "" : "s"}`;
}

type WorkflowRuleDialogProps = {
  open: boolean;
  rule?: WorkflowRule | null;
  onOpenChange: (open: boolean) => void;
  onSaved: (rule: WorkflowRule) => void;
};

function errorMessage(cause: unknown) {
  if (cause instanceof ApiError) {
    if (cause.status === 409) {
      return "Someone else changed this workflow. Close this dialog, reload, and try again.";
    }
    if (cause.status === 403)
      return "Only owners and admins can change workflows.";
    const detail = (cause.body as { detail?: unknown } | null)?.detail;
    if (cause.status === 400 && typeof detail === "string") return detail;
  }
  return "The workflow could not be saved. Please try again.";
}

export function WorkflowRuleDialog({
  open,
  rule,
  onOpenChange,
  onSaved,
}: WorkflowRuleDialogProps) {
  const [name, setName] = useState(rule?.name ?? "");
  const [trigger, setTrigger] = useState<WorkflowTrigger>(
    rule?.trigger ?? "LEAD_CREATED",
  );
  const [action, setAction] = useState<WorkflowAction>(
    rule?.action ?? "ANALYZE_LEAD",
  );
  const [source, setSource] = useState<LeadSource | null>(
    rule?.source_filter ?? null,
  );
  const [delay, setDelay] = useState<number>(rule?.follow_up_delay_hours ?? 24);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const actions = allowedWorkflowActions[trigger];
  const valid = name.trim().length > 0 && actions.includes(action);
  const overlapsAutoStart =
    trigger === "LEAD_CREATED" && action !== "CREATE_FOLLOW_UP";

  function changeTrigger(next: WorkflowTrigger) {
    setTrigger(next);
    if (!allowedWorkflowActions[next].includes(action)) {
      setAction(allowedWorkflowActions[next][0]);
    }
    if (next !== "LEAD_CREATED") setSource(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !valid) return;
    setPending(true);
    setError(null);
    const input = {
      name: name.trim(),
      trigger,
      action,
      source_filter: trigger === "LEAD_CREATED" ? source : null,
      follow_up_delay_hours: action === "CREATE_FOLLOW_UP" ? delay : null,
    };
    try {
      const saved = rule
        ? await updateWorkflow(rule.id, {
            ...input,
            expected_revision: rule.revision,
          })
        : await createWorkflow(input);
      onSaved(saved);
      onOpenChange(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{rule ? "Edit workflow" : "New workflow"}</DialogTitle>
          <DialogDescription>
            Choose what starts the workflow and what it does. New workflows are
            saved turned off, so nothing runs until you switch it on.
          </DialogDescription>
        </DialogHeader>
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <FormField label="Name" htmlFor="workflow-name" required>
            <Input
              id="workflow-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              placeholder="For example: Analyze every website lead"
              autoFocus
              required
            />
          </FormField>
          <FormField label="When" htmlFor="workflow-trigger" required>
            <Select
              id="workflow-trigger"
              value={trigger}
              onChange={(event) =>
                changeTrigger(event.target.value as WorkflowTrigger)
              }
            >
              {Object.entries(workflowTriggerLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          {trigger === "LEAD_CREATED" ? (
            <FormField
              label="Only for leads from"
              htmlFor="workflow-source"
              description="Leave as any source to run for every new lead."
            >
              <Select
                id="workflow-source"
                value={source ?? "any"}
                onChange={(event) =>
                  setSource(
                    event.target.value === "any"
                      ? null
                      : (event.target.value as LeadSource),
                  )
                }
              >
                <option value="any">Any source</option>
                {Object.entries(leadSourceLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : null}
          <FormField
            label="Then"
            htmlFor="workflow-action"
            description={workflowActionHints[action]}
            required
          >
            <Select
              id="workflow-action"
              value={action}
              onChange={(event) =>
                setAction(event.target.value as WorkflowAction)
              }
            >
              {actions.map((value) => (
                <option key={value} value={value}>
                  {workflowActionLabels[value]}
                </option>
              ))}
            </Select>
          </FormField>
          {action === "CREATE_FOLLOW_UP" ? (
            <FormField
              label="Reminder due after"
              htmlFor="workflow-delay"
              required
            >
              <Select
                id="workflow-delay"
                value={String(delay)}
                onChange={(event) => setDelay(Number(event.target.value))}
              >
                {(DELAY_OPTIONS as readonly number[]).includes(delay) ? null : (
                  <option value={delay}>{delayLabel(delay)}</option>
                )}
                {DELAY_OPTIONS.map((hours) => (
                  <option key={hours} value={hours}>
                    {delayLabel(hours)}
                  </option>
                ))}
              </Select>
            </FormField>
          ) : null}
          {trigger === "HUMAN_ATTENTION_REQUIRED" ? (
            <p className="text-muted-foreground text-xs">
              Leads that need a person only get a reminder, so the AI never acts
              on them by itself.
            </p>
          ) : null}
          {overlapsAutoStart ? (
            <p className="text-warning-text text-xs" role="note">
              If Sales Agent auto-start is on in Settings, website leads are
              already analyzed and drafted. Use a source filter to avoid doing
              the same work twice.
            </p>
          ) : null}
          {error ? (
            <p className="text-danger-text text-sm" role="alert">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogCancel>Cancel</DialogCancel>
            <Button type="submit" disabled={pending || !valid}>
              {pending ? "Saving…" : rule ? "Save changes" : "Create workflow"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
