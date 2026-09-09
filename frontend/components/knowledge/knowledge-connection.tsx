import {
  ArrowDown,
  ArrowRight,
  Bot,
  BookOpen,
  MessageSquareText,
  Search,
} from "lucide-react";

import { IndexingStatusBadge } from "@/components/knowledge/indexing-status-badge";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const connectionSteps = [
  { label: "Business knowledge", icon: BookOpen },
  { label: "Knowledge retrieval", icon: Search },
  { label: "AI agent", icon: Bot },
  { label: "Customer response / business action", icon: MessageSquareText },
] as const;

export function KnowledgeConnection() {
  return (
    <Card as="section" aria-labelledby="knowledge-connection-title">
      <CardContent className="grid gap-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3
              id="knowledge-connection-title"
              className="text-base font-medium tracking-tight"
            >
              Knowledge and AI agents
            </h3>
            <p className="text-muted-foreground mt-1 text-sm leading-6">
              A conceptual path for how approved business context may eventually
              support agent work.
            </p>
          </div>
          <StatusBadge status="draft" label="Retrieval unavailable" />
        </div>

        <ol
          className="grid gap-6 md:grid-cols-4"
          aria-label="Conceptual knowledge connection"
        >
          {connectionSteps.map((step, index) => {
            const Icon = step.icon;
            const isLast = index === connectionSteps.length - 1;
            return (
              <li
                key={step.label}
                className="border-border bg-surface-subtle relative flex min-h-24 flex-col items-center justify-center rounded-lg border p-4 text-center"
              >
                <Icon
                  className="text-muted-foreground size-5"
                  aria-hidden="true"
                />
                <span className="mt-2 text-sm font-medium">{step.label}</span>
                {!isLast ? (
                  <>
                    <ArrowDown
                      className="text-muted-foreground absolute top-full left-1/2 mt-1 size-4 -translate-x-1/2 md:hidden"
                      aria-hidden="true"
                    />
                    <ArrowRight
                      className="text-muted-foreground absolute top-1/2 left-full ml-1 size-4 -translate-y-1/2 max-md:hidden"
                      aria-hidden="true"
                    />
                  </>
                ) : null}
              </li>
            );
          })}
        </ol>

        <div className="border-border bg-surface-subtle rounded-lg border p-4">
          <p className="text-sm font-medium">Indexing status concepts</p>
          <p className="text-muted-foreground mt-1 text-xs leading-5">
            These labels define future source states only. No content is being
            processed or indexed.
          </p>
          <div
            className="mt-3 flex flex-wrap gap-2"
            aria-label="Indexing status concepts"
          >
            <IndexingStatusBadge status="ready" />
            <IndexingStatusBadge status="processing" />
            <IndexingStatusBadge status="needs-attention" />
            <IndexingStatusBadge status="not-indexed" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
