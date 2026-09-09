import {
  Building2,
  CircleHelp,
  FileText,
  Globe2,
  Package,
  Scale,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const sourceConcepts = [
  {
    name: "Documents",
    description: "Business files and reference materials.",
    icon: FileText,
  },
  {
    name: "FAQs",
    description: "Approved answers to common questions.",
    icon: CircleHelp,
  },
  {
    name: "Website",
    description: "Selected public website content.",
    icon: Globe2,
  },
  {
    name: "Product information",
    description: "Products, services, and offering details.",
    icon: Package,
  },
  {
    name: "Policies",
    description: "Business rules and operating policies.",
    icon: Scale,
  },
  {
    name: "Company information",
    description: "Organization context and key facts.",
    icon: Building2,
  },
] as const;

export function KnowledgeSourceConcepts() {
  return (
    <ul
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-label="Knowledge source concepts"
    >
      {sourceConcepts.map((source) => {
        const Icon = source.icon;
        return (
          <li key={source.name}>
            <Card as="article" variant="subtle" className="h-full">
              <CardContent className="flex h-full items-start gap-4">
                <div
                  className="bg-card text-muted-foreground border-border flex size-9 shrink-0 items-center justify-center rounded-lg border"
                  aria-hidden="true"
                >
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <h3 className="text-sm font-medium">{source.name}</h3>
                    <StatusBadge status="draft" label="Source concept" />
                  </div>
                  <p className="text-muted-foreground mt-1.5 text-xs leading-5">
                    {source.description}
                  </p>
                </div>
              </CardContent>
            </Card>
          </li>
        );
      })}
    </ul>
  );
}
