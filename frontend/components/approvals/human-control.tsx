import { ShieldCheck } from "lucide-react";

import { RiskBadge } from "@/components/approvals/risk-badge";
import { Card } from "@/components/ui/card";

export function HumanControl() {
  return (
    <Card
      as="section"
      className="grid gap-5 p-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:p-6"
      aria-labelledby="human-control-title"
    >
      <div className="flex items-start gap-3">
        <div
          className="bg-success/10 text-success-text flex size-9 shrink-0 items-center justify-center rounded-lg"
          aria-hidden="true"
        >
          <ShieldCheck className="size-4" />
        </div>
        <div>
          <h3 id="human-control-title" className="text-sm font-medium">
            People remain in control
          </h3>
          <p className="text-muted-foreground mt-1.5 max-w-2xl text-sm leading-6">
            AI can prepare work and recommend actions, while people review
            sensitive decisions before anything is executed.
          </p>
        </div>
      </div>
      <div>
        <p className="text-muted-foreground mb-2 text-xs font-medium">
          Risk labels
        </p>
        <div
          className="flex flex-wrap gap-2"
          aria-label="Available risk levels"
        >
          <RiskBadge level="low" />
          <RiskBadge level="medium" />
          <RiskBadge level="high" />
        </div>
      </div>
    </Card>
  );
}
