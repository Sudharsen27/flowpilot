"use client";

import { useState } from "react";

import { ActivityDetail } from "@/components/activity/activity-detail";
import { ActivityTimeline } from "@/components/activity/activity-timeline";
import { ActivityToolbar } from "@/components/activity/activity-toolbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MobileActivityView = "timeline" | "detail";

export function ActivityWorkspace() {
  const [mobileView, setMobileView] = useState<MobileActivityView>("timeline");

  return (
    <div className="grid gap-3">
      <div
        className="bg-muted grid grid-cols-2 gap-1 rounded-lg p-1 md:hidden"
        role="group"
        aria-label="Mobile activity view"
      >
        <Button
          type="button"
          variant={mobileView === "timeline" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "timeline"}
          aria-controls="activity-timeline-pane"
          onClick={() => setMobileView("timeline")}
        >
          Timeline
        </Button>
        <Button
          type="button"
          variant={mobileView === "detail" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "detail"}
          aria-controls="activity-detail-pane"
          onClick={() => setMobileView("detail")}
        >
          Event detail
        </Button>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(20rem,26rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="activity-timeline-pane"
          className={cn(
            "min-h-[40rem] min-w-0 overflow-hidden",
            mobileView === "timeline" ? "block" : "hidden",
            "md:block",
          )}
          aria-labelledby="activity-timeline-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="activity-timeline-title"
              className="text-base font-medium tracking-tight"
            >
              Activity timeline
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Important events in chronological order.
            </p>
          </header>
          <div className="border-border border-t p-4">
            <ActivityToolbar />
          </div>
          <ActivityTimeline events={[]} />
        </Card>

        <div
          id="activity-detail-pane"
          className={cn(
            "min-w-0",
            mobileView === "detail" ? "block" : "hidden",
            "md:block",
          )}
        >
          <ActivityDetail onBack={() => setMobileView("timeline")} />
        </div>
      </div>
    </div>
  );
}
