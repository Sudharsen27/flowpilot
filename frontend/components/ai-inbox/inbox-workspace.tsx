"use client";

import { useState } from "react";

import { ConversationList } from "@/components/ai-inbox/conversation-list";
import { ConversationWorkspace } from "@/components/ai-inbox/conversation-workspace";
import { InboxToolbar } from "@/components/ai-inbox/inbox-toolbar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type MobileInboxView = "conversations" | "workspace";

export function InboxWorkspace() {
  const [mobileView, setMobileView] =
    useState<MobileInboxView>("conversations");

  return (
    <div className="grid gap-3">
      <div
        className="bg-muted grid grid-cols-2 gap-1 rounded-lg p-1 md:hidden"
        role="group"
        aria-label="Mobile inbox view"
      >
        <Button
          type="button"
          variant={mobileView === "conversations" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "conversations"}
          aria-controls="inbox-conversation-list"
          onClick={() => setMobileView("conversations")}
        >
          Conversations
        </Button>
        <Button
          type="button"
          variant={mobileView === "workspace" ? "secondary" : "ghost"}
          aria-pressed={mobileView === "workspace"}
          aria-controls="inbox-conversation-workspace"
          onClick={() => setMobileView("workspace")}
        >
          Workspace
        </Button>
      </div>

      <div className="grid min-w-0 gap-4 md:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="inbox-conversation-list"
          className={cn(
            "min-h-[42rem] min-w-0 overflow-hidden",
            mobileView === "conversations" ? "block" : "hidden",
            "md:block",
          )}
          aria-labelledby="conversation-list-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="conversation-list-title"
              className="text-base font-medium tracking-tight"
            >
              Conversations
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Customer messages from connected channels.
            </p>
          </header>
          <div className="border-border border-t p-4">
            <InboxToolbar />
          </div>
          <ConversationList conversations={[]} />
        </Card>

        <div
          id="inbox-conversation-workspace"
          className={cn(
            "min-w-0",
            mobileView === "workspace" ? "block" : "hidden",
            "md:block",
          )}
        >
          <ConversationWorkspace
            onBack={() => setMobileView("conversations")}
          />
        </div>
      </div>
    </div>
  );
}
