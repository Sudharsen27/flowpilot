"use client";

import { useState } from "react";

import { ApprovalDetail } from "@/components/approvals/approval-detail";
import { ApprovalQueue } from "@/components/approvals/approval-queue";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MobileApprovalView = "queue" | "detail";

export function ApprovalsWorkspace() {
  const [mobileView, setMobileView] = useState<MobileApprovalView>("queue");

  return (
    <div className="grid gap-3">
      <div
        className="bg-muted grid grid-cols-2 gap-1 rounded-lg p-1 md:hidden"
        role="group"
        aria-label="Mobile approval view"
      >
        <Button
          type="button"
          variant={mobileView === "queue" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "queue"}
          aria-controls="approval-queue-pane"
          onClick={() => setMobileView("queue")}
        >
          Approval queue
        </Button>
        <Button
          type="button"
          variant={mobileView === "detail" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "detail"}
          aria-controls="approval-detail-pane"
          onClick={() => setMobileView("detail")}
        >
          Review detail
        </Button>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="approval-queue-pane"
          className={cn(
            "min-h-[38rem] min-w-0 overflow-hidden",
            mobileView === "queue" ? "block" : "hidden",
            "md:block",
          )}
          aria-labelledby="approval-queue-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="approval-queue-title"
              className="text-base font-medium tracking-tight"
            >
              Approval queue
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Proposed actions waiting for human review.
            </p>
          </header>
          <ApprovalQueue approvals={[]} />
        </Card>

        <div
          id="approval-detail-pane"
          className={cn(
            "min-w-0",
            mobileView === "detail" ? "block" : "hidden",
            "md:block",
          )}
        >
          <ApprovalDetail onBack={() => setMobileView("queue")} />
        </div>
      </div>
    </div>
  );
}
