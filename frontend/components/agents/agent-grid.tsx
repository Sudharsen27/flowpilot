import { Bot, ChevronRight } from "lucide-react";
import Link from "next/link";

import { AgentCard, type AgentCardData } from "@/components/agents/agent-card";
import { EmptyState } from "@/components/empty-state";

const relatedWorkspaces = [
  { href: "/leads", label: "Leads" },
  { href: "/inbox", label: "AI Inbox" },
  { href: "/approvals", label: "Approvals" },
  { href: "/workflows", label: "Workflows" },
] as const;

type AgentGridProps = {
  agents: AgentCardData[];
};

export function AgentGrid({ agents }: AgentGridProps) {
  if (agents.length === 0) {
    return (
      <EmptyState
        icon={<Bot />}
        className="max-w-none"
        title="No agents configured"
        description="Agents will appear here after agent configuration and persistence are implemented. Explore the related workspaces that agents may support in the future."
        action={
          <nav aria-label="Explore related workspaces">
            <ul className="flex flex-wrap gap-2">
              {relatedWorkspaces.map((workspace) => (
                <li key={workspace.href}>
                  <Link
                    href={workspace.href}
                    className="border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
                  >
                    {workspace.label}
                    <ChevronRight className="size-3.5" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        }
      />
    );
  }

  return (
    <ul
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-label="Configured agents"
      data-slot="agent-grid"
    >
      {agents.map((agent) => (
        <li key={agent.id}>
          <AgentCard agent={agent} />
        </li>
      ))}
    </ul>
  );
}
