import { ChevronRight, Plug } from "lucide-react";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";

export function IntegrationSetupState() {
  return (
    <EmptyState
      icon={<Plug />}
      className="max-w-none"
      title="No tools connected"
      description="Integration support and secure connection flows are not implemented. In the future, integrations can allow agents and workflows to work across approved business systems."
      action={
        <nav aria-label="Explore automation workspaces">
          <ul className="flex flex-wrap gap-2">
            <li>
              <Link
                href="/agents"
                className="border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              >
                AI Agents
                <ChevronRight className="size-3.5" aria-hidden="true" />
              </Link>
            </li>
            <li>
              <Link
                href="/workflows"
                className="border-border bg-background hover:bg-muted focus-visible:ring-ring inline-flex min-h-8 items-center gap-1.5 rounded-lg border px-2.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
              >
                Workflows
                <ChevronRight className="size-3.5" aria-hidden="true" />
              </Link>
            </li>
          </ul>
        </nav>
      }
    />
  );
}
