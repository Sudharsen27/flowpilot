import { Bot, Settings2 } from "lucide-react";

import {
  AgentStatusBadge,
  type AgentStatus,
} from "@/components/agents/agent-status-badge";
import { Card, CardContent } from "@/components/ui/card";

export type AgentCardData = {
  id: string;
  name: string;
  purpose: string;
  status: AgentStatus;
  capabilities: string[];
  configurationState: string;
  healthOrLastActivity?: string;
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
            className="bg-muted text-muted-foreground flex size-9 shrink-0 items-center justify-center rounded-lg"
            aria-hidden="true"
          >
            <Bot className="size-4" />
          </div>
          <AgentStatusBadge status={agent.status} />
        </div>

        <div className="mt-5">
          <h3 className="text-base font-medium tracking-tight">{agent.name}</h3>
          <p className="text-muted-foreground mt-1.5 text-sm leading-6">
            {agent.purpose}
          </p>
        </div>

        <div className="mt-5">
          <p className="text-muted-foreground text-xs font-medium">
            Capabilities
          </p>
          <ul className="mt-2 flex flex-wrap gap-2" aria-label="Capabilities">
            {agent.capabilities.map((capability) => (
              <li
                key={capability}
                className="border-border bg-surface-subtle rounded-md border px-2 py-1 text-xs"
              >
                {capability}
              </li>
            ))}
          </ul>
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
            <dt className="text-muted-foreground">Health / last activity</dt>
            <dd className="text-right font-medium">
              {agent.healthOrLastActivity ?? "Unavailable"}
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
