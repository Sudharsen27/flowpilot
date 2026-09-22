import { ShieldCheck } from "lucide-react";

import { Card } from "@/components/ui/card";

export function HumanControl() {
  return (
    <Card
      as="section"
      className="grid gap-5 p-5 sm:items-center sm:p-6"
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
            FlowPilot prepares customer responses for review. Approving a draft
            does not send email — sending is a separate, explicit action.
          </p>
        </div>
      </div>
    </Card>
  );
}
