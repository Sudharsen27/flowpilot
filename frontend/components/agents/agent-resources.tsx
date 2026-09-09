import { BookOpen, Plug } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const tools = ["CRM", "Email", "Calendar", "Messaging", "Webhooks"] as const;
const knowledgeSources = [
  "Company information",
  "Products and services",
  "FAQs",
  "Policies",
  "Documents",
] as const;

type ResourceListProps = {
  items: readonly string[];
  label: string;
};

function ResourceList({ items, label }: ResourceListProps) {
  return (
    <ul className="grid gap-2" aria-label={label}>
      {items.map((item) => (
        <li
          key={item}
          className="border-border bg-surface-subtle flex items-center justify-between gap-3 rounded-md border px-3 py-2 text-sm"
        >
          {item}
          <span className="text-muted-foreground text-xs">Not connected</span>
        </li>
      ))}
    </ul>
  );
}

export function AgentResources() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card as="section" aria-labelledby="agent-tools-title">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle id="agent-tools-title">Tools</CardTitle>
              <CardDescription className="mt-1.5">
                External systems an agent may eventually use within defined
                permissions.
              </CardDescription>
            </div>
            <div
              className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md"
              aria-hidden="true"
            >
              <Plug className="size-4" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge status="draft" label="No tools connected" />
          <ResourceList items={tools} label="Tool connection concepts" />
        </CardContent>
      </Card>

      <Card as="section" aria-labelledby="agent-knowledge-title">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle id="agent-knowledge-title">Knowledge</CardTitle>
              <CardDescription className="mt-1.5">
                Business-specific information an agent may eventually use for
                context.
              </CardDescription>
            </div>
            <div
              className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md"
              aria-hidden="true"
            >
              <BookOpen className="size-4" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-4">
          <StatusBadge status="draft" label="No knowledge connected" />
          <ResourceList
            items={knowledgeSources}
            label="Knowledge source concepts"
          />
        </CardContent>
      </Card>
    </div>
  );
}
