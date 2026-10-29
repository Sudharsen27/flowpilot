import { ArrowRight, Bot } from "lucide-react";
import Link from "next/link";

import { EXECUTION_STATUS_LABELS } from "@/components/agents/execution-status";
import {
  executionCount,
  type ExecutionStatusCounts,
} from "@/components/agents/organization-execution-summary";
import { AiBadge } from "@/components/ai/ai-badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  AGENT_EXECUTION_STATUSES,
  buildAgentExecutionsHref,
} from "@/lib/agent-executions-url";
import { statusPresentation } from "@/lib/status";
import type { Agent } from "@/types/api";

type AiWorkforceStatusProps = {
  loading?: boolean;
  agents: Agent[];
  /** Organization-wide execution counts; `undefined` while loading, `null` when unavailable. */
  executionCounts?: ExecutionStatusCounts | null;
};

function ExecutionCounts({
  counts,
}: {
  counts: ExecutionStatusCounts | null | undefined;
}) {
  if (counts === undefined) {
    return (
      <p className="text-muted-foreground text-sm" role="status">
        Loading agent runs…
      </p>
    );
  }
  if (counts === null) {
    return (
      <p className="text-muted-foreground text-sm">
        Agent run counts are unavailable right now.
      </p>
    );
  }
  return (
    <ul
      className="flex flex-wrap gap-2"
      aria-label="Agent runs by status across your organization"
    >
      {AGENT_EXECUTION_STATUSES.map((status) => {
        const label = EXECUTION_STATUS_LABELS[status];
        const count = executionCount(counts, status);
        const presentation = statusPresentation(status, label);
        return (
          <li key={status}>
            <Link
              href={buildAgentExecutionsHref({ status })}
              aria-label={`${label}: ${count} agent runs`}
              className="border-border hover:bg-muted/60 focus-visible:ring-ring inline-flex items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm outline-none focus-visible:ring-2"
            >
              <StatusBadge status={presentation.status} label={label} />
              <span className="font-semibold tabular-nums">{count}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function AiWorkforceStatus({
  loading = false,
  agents,
  executionCounts,
}: AiWorkforceStatusProps) {
  const active = agents.filter((agent) => agent.status === "ACTIVE").length;
  const ready = agents.filter((agent) => agent.status === "READY").length;
  const configured = agents.length > 0;
  const badge = configured
    ? statusPresentation(
        active > 0 ? "ACTIVE" : ready > 0 ? "READY" : "DRAFT",
        active > 0
          ? `${active} active`
          : ready > 0
            ? `${ready} ready`
            : "Configured",
      )
    : statusPresentation("DRAFT", "No agents yet");

  return (
    <Card as="section" variant="information">
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3">
            <span
              className="bg-ai/10 text-ai-text border-ai-border flex size-9 shrink-0 items-center justify-center rounded-md border"
              aria-hidden="true"
            >
              <Bot className="size-4" />
            </span>
            <div>
              <CardTitle>AI workforce</CardTitle>
              <CardDescription className="mt-1">
                Agents configured for this organization. Sales runs use the Sales
                Agent pipeline, not the generic debugger.
              </CardDescription>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2" aria-label="AI workforce status">
            <AiBadge label="Agent" />
            <StatusBadge status={badge.status} label={loading ? "Loading" : badge.label} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        {loading ? (
          <p className="text-muted-foreground max-w-2xl text-sm leading-6">
            Loading agents…
          </p>
        ) : configured ? (
          <p className="text-muted-foreground max-w-2xl text-sm leading-6">
            {agents.length} configured agent{agents.length === 1 ? "" : "s"} in
            this organization. {active ? `${active} active` : "No active agents"}
            {ready ? `, ${ready} ready` : ""}.
          </p>
        ) : (
          <p className="text-muted-foreground max-w-2xl text-sm leading-6">
            No agents are configured yet. Create a Sales Agent to start qualifying
            enquiries.
          </p>
        )}
        <div className="mt-4 grid gap-2">
          <h3 className="text-sm font-medium">Agent runs</h3>
          <ExecutionCounts counts={executionCounts} />
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
          Review AI Agents
          <ArrowRight aria-hidden="true" />
        </Link>
        <Link
          href={buildAgentExecutionsHref()}
          className={buttonVariants({ variant: "outline" })}
        >
          View all agent runs
          <ArrowRight aria-hidden="true" />
        </Link>
      </CardFooter>
    </Card>
  );
}
