"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { AiBadge } from "@/components/ai/ai-badge";
import { StatePanel } from "@/components/data-display/state-panel";
import { FormField } from "@/components/forms/form-field";
import { Select } from "@/components/forms/select";
import { Textarea } from "@/components/forms/textarea";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogCancel,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getAgents } from "@/lib/api/agents";
import { ApiError } from "@/lib/api/client";
import { startLeadSalesRun } from "@/lib/api/sales-runs";
import type { Agent, Lead, SalesRun } from "@/types/api";

type StartLeadSalesRunDialogProps = {
  open: boolean;
  lead: Lead | null;
  onOpenChange: (open: boolean) => void;
  onCompleted: (result: SalesRun) => void;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function errorMessage(cause: unknown) {
  if (!(cause instanceof ApiError)) {
    return "The sales run could not be started. Please try again.";
  }
  if (cause.status === 409 && isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  if (cause.status === 503) {
    return "AI provider is not configured.";
  }
  if (cause.status === 422) {
    return "Review the enquiry and Sales Agent.";
  }
  if (isRecord(cause.body) && typeof cause.body.detail === "string") {
    return cause.body.detail;
  }
  return "The sales run could not be started. Please try again.";
}

function isEligibleSalesAgent(agent: Agent) {
  return (
    agent.agent_type === "SALES" &&
    (agent.status === "READY" || agent.status === "ACTIVE")
  );
}

export function StartLeadSalesRunDialog({
  open,
  lead,
  onOpenChange,
  onCompleted,
}: StartLeadSalesRunDialogProps) {
  const [enquiry, setEnquiry] = useState("");
  const [agentId, setAgentId] = useState("");
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [agentLoadKey, setAgentLoadKey] = useState(0);

  const eligible = useMemo(
    () => agents.filter(isEligibleSalesAgent),
    [agents],
  );

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void getAgents({ agentType: "SALES" })
      .then((data) => {
        if (cancelled) return;
        const ready = data.filter(isEligibleSalesAgent);
        setAgents(data);
        setAgentsError(false);
        setAgentId((current) => {
          if (current && ready.some((agent) => agent.id === current)) {
            return current;
          }
          return ready.length === 1 ? ready[0]!.id : "";
        });
      })
      .catch(() => {
        if (!cancelled) {
          setAgentsError(true);
          setAgents([]);
        }
      })
      .finally(() => {
        if (!cancelled) setAgentsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, agentLoadKey]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lead || pending) return;
    const trimmedEnquiry = enquiry.trim();
    if (!trimmedEnquiry) {
      setFieldError("Enquiry is required.");
      return;
    }
    if (!agentId) {
      setFieldError("Select a Sales Agent.");
      return;
    }
    setFieldError(null);
    setError(null);
    setPending(true);
    try {
      const result = await startLeadSalesRun(lead.id, {
        enquiry: trimmedEnquiry,
        agent_id: agentId,
      });
      setEnquiry("");
      onCompleted(result);
      onOpenChange(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }

  const unavailable = !agentsLoading && !agentsError && eligible.length === 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        if (!next) {
          setError(null);
          setFieldError(null);
        }
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <div className="flex items-center gap-2">
            <DialogTitle>Start Sales Agent</DialogTitle>
            <AiBadge label="Agent" />
          </div>
          <DialogDescription>
            This Sales Agent will qualify the enquiry and prepare a response for
            review. It will not send the email.
          </DialogDescription>
        </DialogHeader>
        {agentsError ? (
          <div className="mt-4 grid gap-4">
            <StatePanel
              kind="error"
              className="max-w-none"
              title="Sales Agents could not be loaded"
              description="Retry to load Sales Agents for this organization."
              action={
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setAgentsLoading(true);
                    setAgentsError(false);
                    setAgentLoadKey((value) => value + 1);
                  }}
                >
                  Retry
                </Button>
              }
            />
            <DialogFooter>
              <DialogCancel>Close</DialogCancel>
            </DialogFooter>
          </div>
        ) : unavailable ? (
          <div className="mt-4 grid gap-4">
            <StatePanel
              kind="unavailable"
              className="max-w-none"
              title="No Sales Agent is ready"
              description="No Sales Agent is ready. Open AI Agents to finish setup."
              action={
                <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
                  Open AI Agents
                </Link>
              }
            />
            <DialogFooter>
              <DialogCancel>Close</DialogCancel>
            </DialogFooter>
          </div>
        ) : (
          <form className="mt-4 grid gap-4" onSubmit={handleSubmit}>
            <FormField
              label="Enquiry"
              htmlFor="lead-sales-run-enquiry"
              required
              error={fieldError}
            >
              <Textarea
                id="lead-sales-run-enquiry"
                value={enquiry}
                onChange={(event) => setEnquiry(event.target.value)}
                maxLength={8000}
                disabled={pending || agentsLoading}
                aria-invalid={fieldError ? true : undefined}
              />
            </FormField>
            <FormField label="Sales Agent" htmlFor="lead-sales-run-agent" required>
              <Select
                id="lead-sales-run-agent"
                value={agentId}
                onChange={(event) => setAgentId(event.target.value)}
                disabled={pending || agentsLoading}
              >
                <option value="">
                  {agentsLoading ? "Loading Sales Agents…" : "Select a Sales Agent"}
                </option>
                {eligible.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </Select>
            </FormField>
            <dl className="grid gap-3">
              <div>
                <dt className="text-muted-foreground text-xs font-medium">Lead</dt>
                <dd className="mt-1 text-sm">{lead?.name ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground text-xs font-medium">Email</dt>
                <dd className="text-muted-foreground mt-1 text-sm">
                  {lead?.email || "—"}
                </dd>
              </div>
            </dl>
            {error ? (
              <p className="text-danger-text text-sm" role="alert">
                {error}
              </p>
            ) : null}
            <DialogFooter>
              <DialogCancel>Close</DialogCancel>
              <Button type="submit" disabled={pending || agentsLoading || !agentId}>
                {pending ? "Starting…" : "Start"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
