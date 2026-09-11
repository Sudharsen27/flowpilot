import { Bot, Settings2 } from "lucide-react";
import Link from "next/link";

import {
  AgentStatusBadge,
  type AgentStatus,
} from "@/components/agents/agent-status-badge";
import { Card, CardContent } from "@/components/ui/card";

export type AgentCardData = {
  id: string;
  name: string;
  description: string;
  agentType: string;
  status: AgentStatus;
  configurationState: string;
  updatedAt: string;
};

type AgentCardProps = {
  agent: AgentCardData;
};

export function AgentCard({ agent }: AgentCardProps) {
  return (
    <Card as="article" className="h-full">
      <CardContent className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-3">
          <div
            className="bg-ai/10 text-ai-text border-ai-border flex size-9 shrink-0 items-center justify-center rounded-lg border"
            aria-hidden="true"
          >
            <Bot className="size-4" />
          </div>
          <AgentStatusBadge status={agent.status} />
        </div>

        <div className="mt-5">
          <h3 className="text-base font-medium tracking-tight">
            <Link
              href={`/agents/${agent.id}`}
              className="focus-visible:ring-ring rounded-sm outline-none hover:underline focus-visible:ring-2"
            >
              {agent.name}
            </Link>
          </h3>
          <p className="text-muted-foreground mt-1.5 text-sm leading-6">
            {agent.description || "No description provided."}
          </p>
        </div>

        <div className="mt-5">
          <p className="text-muted-foreground text-xs font-medium">Agent type</p>
          <p className="border-border bg-surface-subtle mt-2 inline-flex rounded-md border px-2 py-1 text-xs">
            {agent.agentType}
          </p>
        </div>

        <dl className="border-border mt-5 grid gap-3 border-t pt-4 text-xs">
          <div className="flex items-start justify-between gap-3">
            <dt className="text-muted-foreground flex items-center gap-1.5">
              <Settings2 className="size-3.5" aria-hidden="true" />
              Configuration
            </dt>
            <dd className="text-right font-medium">
              {agent.configurationState}
            </dd>
          </div>
          <div className="flex items-start justify-between gap-3">
            <dt className="text-muted-foreground">Updated</dt>
            <dd className="text-right font-medium">{agent.updatedAt}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
