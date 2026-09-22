"use client";

import { useEffect, useState } from "react";

import {
  ConversationList,
  type ConversationListItem,
  type ConversationStatus,
} from "@/components/ai-inbox/conversation-list";
import { ConversationWorkspace } from "@/components/ai-inbox/conversation-workspace";
import {
  InboxToolbar,
  type NeedsApprovalFilter,
} from "@/components/ai-inbox/inbox-toolbar";
import { formatTimestamp } from "@/components/agents/execution-status";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getInbox, getInboxConversation } from "@/lib/api/inbox";
import { cn } from "@/lib/utils";
import type {
  InboxConversationResponse,
  InboxConversationState,
  InboxItem,
  InboxListResponse,
  LeadSource,
} from "@/types/api";

const PAGE_SIZE = 20;

type MobileInboxView = "conversations" | "workspace";

type InboxWorkspaceProps = {
  onSummary?: (page: InboxListResponse | null) => void;
};

const stateToStatus: Record<InboxConversationState, ConversationStatus> = {
  OPEN: "open",
  NEEDS_APPROVAL: "waiting",
  CLOSED: "resolved",
};

function toListItem(item: InboxItem): ConversationListItem {
  return {
    id: item.lead_id,
    contactName: item.name,
    company: item.company ?? undefined,
    status: stateToStatus[item.conversation_state],
    lastMessagePreview: item.preview ?? undefined,
    timeLabel: formatTimestamp(item.last_activity_at) ?? undefined,
    needsApproval: item.needs_approval,
  };
}

export function InboxWorkspace({ onSummary }: InboxWorkspaceProps) {
  const [mobileView, setMobileView] = useState<MobileInboxView>("conversations");
  const [query, setQuery] = useState("");
  const [conversationState, setConversationState] = useState<
    InboxConversationState | ""
  >("");
  const [source, setSource] = useState<LeadSource | "">("");
  const [needsApproval, setNeedsApproval] = useState<NeedsApprovalFilter>("");
  const [offset, setOffset] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<InboxListResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [conversation, setConversation] =
    useState<InboxConversationResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getInbox({
      q: query.trim() || undefined,
      conversation_state: conversationState || undefined,
      source: source || undefined,
      needs_approval:
        needsApproval === "" ? undefined : needsApproval === "true",
      limit: PAGE_SIZE,
      offset,
    })
      .then((data) => {
        if (cancelled) return;
        setPage(data);
        onSummary?.(data);
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setPage(null);
        onSummary?.(null);
        setError(
          cause instanceof ApiError && cause.status === 401
            ? "Your session has expired. Sign in again to view the Inbox."
            : "Inbox could not be loaded.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    conversationState,
    needsApproval,
    offset,
    onSummary,
    query,
    retryKey,
    source,
  ]);

  function beginFetch() {
    setLoading(true);
    setError(null);
  }

  function loadConversation(leadId: string) {
    setSelectedId(leadId);
    setDetailLoading(true);
    setDetailError(null);
    setMobileView("workspace");
    void getInboxConversation(leadId)
      .then((data) => {
        setConversation(data);
      })
      .catch((cause: unknown) => {
        setConversation(null);
        setDetailError(
          cause instanceof ApiError && cause.status === 401
            ? "Your session has expired. Sign in again to view this conversation."
            : cause instanceof ApiError && cause.status === 404
              ? "This conversation could not be found."
              : "Conversation could not be loaded.",
        );
      })
      .finally(() => {
        setDetailLoading(false);
      });
  }

  const hasFilters =
    query.trim() !== "" ||
    conversationState !== "" ||
    source !== "" ||
    needsApproval !== "";
  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);
  const conversations = (page?.items ?? []).map(toListItem);

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
              Sales conversation history for this organization.
            </p>
          </header>
          <div className="border-border border-t p-4">
            <InboxToolbar
              query={query}
              conversationState={conversationState}
              source={source}
              needsApproval={needsApproval}
              onQueryChange={(value) => {
                beginFetch();
                setQuery(value);
                setOffset(0);
              }}
              onConversationStateChange={(value) => {
                beginFetch();
                setConversationState(value);
                setOffset(0);
              }}
              onSourceChange={(value) => {
                beginFetch();
                setSource(value);
                setOffset(0);
              }}
              onNeedsApprovalChange={(value) => {
                beginFetch();
                setNeedsApproval(value);
                setOffset(0);
              }}
              onClearFilters={() => {
                beginFetch();
                setQuery("");
                setConversationState("");
                setSource("");
                setNeedsApproval("");
                setOffset(0);
              }}
            />
          </div>
          {error ? (
            <div className="p-4">
              <StatePanel
                kind="error"
                title="Inbox could not be loaded"
                description={error}
                action={
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      beginFetch();
                      setRetryKey((value) => value + 1);
                    }}
                  >
                    Retry
                  </Button>
                }
              />
            </div>
          ) : loading && page === null ? (
            <div className="grid gap-3 p-4" role="status">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <span className="sr-only">Loading conversations</span>
            </div>
          ) : !loading && page && page.total === 0 && hasFilters ? (
            <div className="p-4">
              <StatePanel
                title="No matching conversations"
                description="Nothing matches the current search or filters."
              />
            </div>
          ) : (
            <ConversationList
              conversations={conversations}
              selectedId={selectedId ?? undefined}
              onSelect={(item) => {
                loadConversation(item.id);
              }}
            />
          )}
          {total > 0 ? (
            <div className="border-border flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3">
              <p className="text-muted-foreground text-sm">
                Showing {start}–{end} of {total}
              </p>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={offset === 0 || loading}
                  onClick={() => {
                    beginFetch();
                    setOffset(Math.max(0, offset - PAGE_SIZE));
                  }}
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={offset + PAGE_SIZE >= total || loading}
                  onClick={() => {
                    beginFetch();
                    setOffset(offset + PAGE_SIZE);
                  }}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
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
            conversation={conversation}
            loading={detailLoading}
            error={detailError}
            onRetry={
              selectedId
                ? () => {
                    loadConversation(selectedId);
                  }
                : undefined
            }
            onBack={() => setMobileView("conversations")}
          />
        </div>
      </div>
    </div>
  );
}
