"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Agent } from "@/types/api";

function isEligibleSalesAgent(agent: Agent) {
  return (
    agent.agent_type === "SALES" &&
    (agent.status === "READY" || agent.status === "ACTIVE")
  );
}

export function salesCopilotHref(agentId: string, leadId: string) {
  const params = new URLSearchParams({ lead: leadId });
  return `/agents/${encodeURIComponent(agentId)}/workspace?${params.toString()}`;
}

type AskSalesCopilotProps = {
  leadId: string;
  agents: Agent[];
};

export function AskSalesCopilot({ leadId, agents }: AskSalesCopilotProps) {
  const eligible = agents.filter(isEligibleSalesAgent);
  const [open, setOpen] = useState(false);
  const [agentId, setAgentId] = useState(eligible[0]?.id ?? "");
  const selectedId = eligible.some((agent) => agent.id === agentId)
    ? agentId
    : (eligible[0]?.id ?? "");

  if (eligible.length === 0) return null;

  if (eligible.length === 1) {
    return (
      <Link
        href={salesCopilotHref(eligible[0]!.id, leadId)}
        className={buttonVariants({ variant: "outline" })}
      >
        Ask Sales Copilot
      </Link>
    );
  }

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)}>
        Ask Sales Copilot
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ask Sales Copilot</DialogTitle>
            <DialogDescription>
              Choose the Sales Agent that should use this lead&apos;s stored
              enquiry. Nothing is sent from the copilot.
            </DialogDescription>
          </DialogHeader>
          <form className="mt-4 grid gap-4">
            <label className="grid gap-1.5 text-sm" htmlFor="sales-copilot-agent">
              Sales Agent
              <select
                id="sales-copilot-agent"
                className="border-input bg-background h-9 rounded-md border px-3"
                value={selectedId}
                onChange={(event) => setAgentId(event.target.value)}
              >
                {eligible.map((agent) => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex justify-end">
              <Link
                href={salesCopilotHref(selectedId, leadId)}
                className={buttonVariants()}
              >
                Continue
              </Link>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
