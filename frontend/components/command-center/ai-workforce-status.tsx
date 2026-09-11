import { ArrowRight, Bot } from "lucide-react";
import Link from "next/link";

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
import { statusPresentation } from "@/lib/status";
import type { Agent } from "@/types/api";

type AiWorkforceStatusProps = {
  loading?: boolean;
  agents: Agent[];
};

export function AiWorkforceStatus({
  loading = false,
  agents,
}: AiWorkforceStatusProps) {
  const active = agents.filter((agent) => agent.status === "ACTIVE").length;
  const ready = agents.filter((agent) => agent.status === "READY").length;
  const configured = agents.length > 0;
  const badge = configured
    ? statusPresentation("ACTIVE", `${agents.length} agent${agents.length === 1 ? "" : "s"}`)
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
          <div className="flex flex-wrap items-center gap-2">
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
            {agents.length} agent{agents.length === 1 ? "" : "s"} in this
            organization
            {active ? `, ${active} active` : ""}
            {ready ? `, ${ready} ready` : ""}. Per-agent execution history is
            available on each agent detail page.
          </p>
        ) : (
          <p className="text-muted-foreground max-w-2xl text-sm leading-6">
            No agents are configured yet. Create a Sales Agent to start qualifying
            enquiries.
          </p>
        )}
      </CardContent>
      <CardFooter>
        <Link href="/agents" className={buttonVariants({ variant: "outline" })}>
          Review AI Agents
          <ArrowRight aria-hidden="true" />
        </Link>
      </CardFooter>
    </Card>
  );
}
