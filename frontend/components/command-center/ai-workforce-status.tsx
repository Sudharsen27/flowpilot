import { ArrowRight, Bot } from "lucide-react";
import Link from "next/link";

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

export function AiWorkforceStatus() {
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
                Configure the agents that will support your business operations.
              </CardDescription>
            </div>
          </div>
          <StatusBadge status="draft" label="Not configured" />
        </div>
      </CardHeader>
      <CardContent className="pt-4">
        <p className="text-muted-foreground max-w-2xl text-sm leading-6">
          No live agent runtime is connected yet. Agent status and execution
          activity will appear here after that capability is implemented.
        </p>
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
