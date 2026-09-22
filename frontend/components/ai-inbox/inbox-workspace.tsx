"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import {
  ConversationList,
  type ConversationListItem,
  type ConversationStatus,
} from "@/components/ai-inbox/conversation-list";
import { ConversationWorkspace } from "@/components/ai-inbox/conversation-workspace";
import { InboxToolbar } from "@/components/ai-inbox/inbox-toolbar";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getInbox, getInboxConversation } from "@/lib/api/inbox";
import {
  INBOX_PAGE_SIZE,
  type InboxUrlState,
  inboxUrlEquals,
  parseInboxSearchParams,
  serializeInboxSearchParams,
} from "@/lib/inbox-url";
import { cn } from "@/lib/utils";
import type {
  InboxConversationResponse,
  InboxConversationState,
  InboxItem,
  InboxListResponse,
} from "@/types/api";

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
    source: item.source,
    status: stateToStatus[item.conversation_state],
    lastMessagePreview: item.preview ?? undefined,
    occurredAt: item.last_activity_at,
    needsApproval: item.needs_approval,
  };
}

function listFilterKey(state: InboxUrlState) {
  return serializeInboxSearchParams({ ...state, leadId: null });
}

function listSkeleton() {
  return (
    <div className="grid gap-0" role="status">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="border-border space-y-2 border-b p-4">
          <div className="flex justify-between gap-3">
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-12" />
          </div>
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-full" />
        </div>
      ))}
      <span className="sr-only">Loading conversations</span>
    </div>
  );
}

export function InboxWorkspace({ onSummary }: InboxWorkspaceProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlState = useMemo(
    () => parseInboxSearchParams(searchParams),
    [searchParams],
  );
  const filterKey = listFilterKey(urlState);

  const [mobileView, setMobileView] = useState<MobileInboxView>(
    urlState.leadId ? "workspace" : "conversations",
  );
  const [queryInput, setQueryInput] = useState(urlState.q);
  const [trackedUrlQuery, setTrackedUrlQuery] = useState(urlState.q);
  const [trackedFilterKey, setTrackedFilterKey] = useState(filterKey);
  const [trackedLeadId, setTrackedLeadId] = useState(urlState.leadId);
  const [retryKey, setRetryKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<InboxListResponse | null>(null);
  const [conversation, setConversation] =
    useState<InboxConversationResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(Boolean(urlState.leadId));
  const [detailError, setDetailError] = useState<string | null>(null);
  const requestLeadRef = useRef<string | null>(urlState.leadId);

  if (urlState.q !== trackedUrlQuery) {
    setTrackedUrlQuery(urlState.q);
    setQueryInput(urlState.q);
  }
  if (filterKey !== trackedFilterKey) {
    setTrackedFilterKey(filterKey);
    setLoading(true);
    setError(null);
  }
  if (urlState.leadId !== trackedLeadId) {
    setTrackedLeadId(urlState.leadId);
    if (urlState.leadId) {
      setDetailLoading(true);
      setDetailError(null);
      setMobileView("workspace");
    }
  }

  const replaceUrl = useCallback(
    (next: InboxUrlState) => {
      const serialized = serializeInboxSearchParams(next);
      if (serialized === searchParams.toString()) return;
      router.replace(serialized ? `${pathname}?${serialized}` : pathname, {
        scroll: false,
      });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = queryInput.trim();
      if (trimmed === urlState.q) return;
      replaceUrl({ ...urlState, q: trimmed, offset: 0 });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [queryInput, replaceUrl, urlState]);

  useEffect(() => {
    let cancelled = false;
    void getInbox({
      q: urlState.q || undefined,
      conversation_state: urlState.conversationState || undefined,
      source: urlState.source || undefined,
      needs_approval:
        urlState.needsApproval === ""
          ? undefined
          : urlState.needsApproval === "true",
      limit: INBOX_PAGE_SIZE,
      offset: urlState.offset,
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
            : "Something went wrong while loading this Inbox.",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filterKey, onSummary, retryKey, urlState]);

  useEffect(() => {
    const leadId = urlState.leadId;
    if (!leadId) {
      requestLeadRef.current = null;
      return;
    }
    requestLeadRef.current = leadId;
    let cancelled = false;
    void getInboxConversation(leadId)
      .then((data) => {
        if (cancelled || requestLeadRef.current !== leadId) return;
        setConversation(data);
      })
      .catch((cause: unknown) => {
        if (cancelled || requestLeadRef.current !== leadId) return;
        setConversation(null);
        setDetailError(
          cause instanceof ApiError && cause.status === 401
            ? "Your session has expired. Sign in again to view this conversation."
            : cause instanceof ApiError && cause.status === 404
              ? "This conversation could not be found."
              : "Unable to load this conversation.",
        );
      })
      .finally(() => {
        if (!cancelled && requestLeadRef.current === leadId) {
          setDetailLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey, urlState.leadId]);

  function patchUrl(patch: Partial<InboxUrlState>) {
    const next = { ...urlState, ...patch };
    if (inboxUrlEquals(next, urlState)) return;
    replaceUrl(next);
  }

  function clearFilters() {
    setQueryInput("");
    setTrackedUrlQuery("");
    replaceUrl({
      ...urlState,
      q: "",
      conversationState: "",
      source: "",
      needsApproval: "",
      offset: 0,
    });
  }

  function retryList() {
    setLoading(true);
    setError(null);
    setRetryKey((value) => value + 1);
  }

  function retryDetail() {
    if (!urlState.leadId) return;
    setDetailLoading(true);
    setDetailError(null);
    setRetryKey((value) => value + 1);
  }

  const hasFilters =
    urlState.q !== "" ||
    urlState.conversationState !== "" ||
    urlState.source !== "" ||
    urlState.needsApproval !== "";
  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : urlState.offset + 1;
  const end = Math.min(urlState.offset + INBOX_PAGE_SIZE, total);
  const conversations = (page?.items ?? []).map(toListItem);
  const selectedLeadId = urlState.leadId;
  const activeConversation = selectedLeadId ? conversation : null;
  const activeDetailError = selectedLeadId ? detailError : null;
  const activeDetailLoading = selectedLeadId ? detailLoading : false;

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

      <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)]">
        <Card
          as="section"
          id="inbox-conversation-list"
          className={cn(
            "min-h-[42rem] min-w-0 overflow-hidden",
            mobileView === "conversations" ? "block" : "hidden",
            "lg:block",
          )}
          aria-labelledby="conversation-list-title"
        >
          <header className="px-4 pt-4 pb-3 sm:px-5">
            <h3
              id="conversation-list-title"
              className="text-base font-semibold tracking-tight"
            >
              Conversations
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Customers and AI-assisted sales activity that need attention.
            </p>
          </header>
          <div className="border-border border-t p-4">
            <InboxToolbar
              query={queryInput}
              conversationState={urlState.conversationState}
              source={urlState.source}
              needsApproval={urlState.needsApproval}
              onQueryChange={setQueryInput}
              onConversationStateChange={(value) =>
                patchUrl({ conversationState: value, offset: 0 })
              }
              onSourceChange={(value) => patchUrl({ source: value, offset: 0 })}
              onNeedsApprovalChange={(value) =>
                patchUrl({ needsApproval: value, offset: 0 })
              }
              onClearFilters={clearFilters}
            />
          </div>
          {error ? (
            <div className="p-4">
              <StatePanel
                kind="error"
                title="Unable to load conversations"
                description={error}
                action={
                  <Button type="button" variant="outline" onClick={retryList}>
                    Retry
                  </Button>
                }
              />
            </div>
          ) : loading && page === null ? (
            listSkeleton()
          ) : !loading && page && page.total === 0 && hasFilters ? (
            <div className="p-4">
              <StatePanel
                title="No conversations match these filters"
                description="Try a different search or clear filters to see all Inbox conversations."
                action={
                  <Button type="button" variant="outline" onClick={clearFilters}>
                    Clear filters
                  </Button>
                }
              />
            </div>
          ) : (
            <ConversationList
              conversations={conversations}
              selectedId={selectedLeadId ?? undefined}
              onSelect={(item) => {
                patchUrl({ leadId: item.id });
                setMobileView("workspace");
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
                  disabled={urlState.offset === 0 || loading}
                  onClick={() =>
                    patchUrl({
                      offset: Math.max(0, urlState.offset - INBOX_PAGE_SIZE),
                    })
                  }
                >
                  Previous
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  disabled={
                    urlState.offset + INBOX_PAGE_SIZE >= total || loading
                  }
                  onClick={() =>
                    patchUrl({ offset: urlState.offset + INBOX_PAGE_SIZE })
                  }
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
            "lg:block",
          )}
        >
          <ConversationWorkspace
            conversation={activeConversation}
            loading={activeDetailLoading}
            error={activeDetailError}
            onRetry={selectedLeadId ? retryDetail : undefined}
            onBack={() => setMobileView("conversations")}
          />
        </div>
      </div>
    </div>
  );
}
