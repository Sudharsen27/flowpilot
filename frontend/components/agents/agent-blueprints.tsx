import { Headphones, MessageSquare, Settings2, TrendingUp } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const agentBlueprints = [
  {
    name: "Sales Agent",
    purpose:
      "A future configuration for handling sales enquiries and follow-up.",
    capabilities: [
      "Understand enquiries",
      "Qualify leads",
      "Schedule follow-ups",
    ],
    icon: TrendingUp,
  },
  {
    name: "Support Agent",
    purpose: "A future configuration for assisting with customer questions.",
    capabilities: [
      "Understand requests",
      "Respond to customers",
      "Escalate to humans",
    ],
    icon: Headphones,
  },
  {
    name: "Operations Agent",
    purpose: "A future configuration for coordinating operational work.",
    capabilities: [
      "Create or update records",
      "Coordinate tasks",
      "Escalate exceptions",
    ],
    icon: Settings2,
  },
  {
    name: "Communication Agent",
    purpose: "A future configuration for preparing business communications.",
    capabilities: [
      "Prepare responses",
      "Schedule follow-ups",
      "Request human review",
    ],
    icon: MessageSquare,
  },
] as const;

export function AgentBlueprints() {
  return (
    <ul
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      aria-label="Planned agent blueprints"
    >
      {agentBlueprints.map((blueprint) => {
        const Icon = blueprint.icon;
        return (
          <li key={blueprint.name}>
            <Card as="article" variant="subtle" className="h-full">
              <CardContent className="flex h-full flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div
                    className="bg-card text-muted-foreground border-border flex size-9 items-center justify-center rounded-lg border"
                    aria-hidden="true"
                  >
                    <Icon className="size-4" />
                  </div>
                  <StatusBadge status="draft" label="Blueprint only" />
                </div>
                <h3 className="mt-5 text-sm font-medium">{blueprint.name}</h3>
                <p className="text-muted-foreground mt-1.5 text-xs leading-5">
                  {blueprint.purpose}
                </p>
                <div className="border-border mt-4 border-t pt-4">
                  <p className="text-muted-foreground text-xs font-medium">
                    Capability concepts
                  </p>
                  <ul className="mt-2 grid gap-2">
                    {blueprint.capabilities.map((capability) => (
                      <li
                        key={capability}
                        className="flex items-start gap-2 text-xs"
                      >
                        <span
                          className="bg-muted-foreground mt-1.5 size-1 shrink-0 rounded-full"
                          aria-hidden="true"
                        />
                        {capability}
                      </li>
                    ))}
                  </ul>
                </div>
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
