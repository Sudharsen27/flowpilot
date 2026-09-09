import {
  ArrowUpRight,
  Bot,
  CheckCheck,
  Inbox,
  Users,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { Card, CardContent } from "@/components/ui/card";

const quickActions = [
  {
    href: "/agents",
    label: "AI Agents",
    description: "Review agent setup and configuration.",
    icon: Bot,
  },
  {
    href: "/leads",
    label: "Leads",
    description: "Open the leads workspace.",
    icon: Users,
  },
  {
    href: "/inbox",
    label: "AI Inbox",
    description: "Open the shared AI inbox.",
    icon: Inbox,
  },
  {
    href: "/approvals",
    label: "Approvals",
    description: "Review the approvals workspace.",
    icon: CheckCheck,
  },
  {
    href: "/workflows",
    label: "Workflows",
    description: "Review workflow setup.",
    icon: Workflow,
  },
] as const;

export function QuickActions() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {quickActions.map((action) => {
        const Icon = action.icon;
        return (
          <Link
            key={action.href}
            href={action.href}
            className="focus-visible:ring-ring rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-offset-2"
          >
            <Card variant="interactive" className="h-full transition-colors">
              <CardContent className="flex h-full min-h-32 flex-col justify-between gap-4">
                <div className="flex items-start justify-between gap-3">
                  <span
                    className="bg-muted text-muted-foreground flex size-8 items-center justify-center rounded-md"
                    aria-hidden="true"
                  >
                    <Icon className="size-4" />
                  </span>
                  <ArrowUpRight
                    className="text-muted-foreground size-4"
                    aria-hidden="true"
                  />
                </div>
                <div>
                  <h3 className="text-sm font-medium">{action.label}</h3>
                  <p className="text-muted-foreground mt-1 text-xs leading-5">
                    {action.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          </Link>
        );
      })}
    </div>
  );
}
