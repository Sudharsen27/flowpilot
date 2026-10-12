"use client";

import { BookOpen, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { EmptyState } from "@/components/empty-state";
import { FilterBar } from "@/components/forms/filter-bar";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import { KnowledgeEntryDialog } from "@/components/knowledge/knowledge-entry-dialog";
import { KnowledgeEntryList } from "@/components/knowledge/knowledge-entry-list";
import { knowledgeCategoryLabels } from "@/components/knowledge/knowledge-labels";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import {
  deleteKnowledgeEntry,
  listKnowledge,
  updateKnowledgeEntry,
} from "@/lib/api/knowledge";
import type {
  KnowledgeCategory,
  KnowledgeEntry,
  KnowledgeEntryStatus,
  KnowledgeListResponse,
} from "@/types/api";

export default function KnowledgePage() {
  const { session } = useAuth();
  const role = session?.membership.role;
  const canManage = role === "OWNER" || role === "ADMIN";

  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<KnowledgeCategory | null>(null);
  const [status, setStatus] = useState<KnowledgeEntryStatus>("ACTIVE");
  const [data, setData] = useState<KnowledgeListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogKey, setDialogKey] = useState(0);
  const [editing, setEditing] = useState<KnowledgeEntry | null>(null);
  const [deleting, setDeleting] = useState<KnowledgeEntry | null>(null);
  const [busyEntryId, setBusyEntryId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(() => setSearch(query.trim()), 250);
    return () => clearTimeout(handle);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    void listKnowledge({ category, status, q: search })
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setData(null);
        setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [category, status, search, reloadKey]);

  function reload() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function openDialog(entry: KnowledgeEntry | null) {
    setEditing(entry);
    setDialogKey((value) => value + 1);
    setDialogOpen(true);
  }

  async function toggleArchive(entry: KnowledgeEntry) {
    setBusyEntryId(entry.id);
    setActionError(null);
    try {
      await updateKnowledgeEntry(entry.id, {
        expected_revision: entry.revision,
        status: entry.status === "ARCHIVED" ? "ACTIVE" : "ARCHIVED",
      });
      reload();
    } catch {
      setActionError(
        `“${entry.title}” could not be updated. Reload and try again.`,
      );
    } finally {
      setBusyEntryId(null);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    const entry = deleting;
    setBusyEntryId(entry.id);
    setActionError(null);
    try {
      await deleteKnowledgeEntry(entry.id);
      setDeleting(null);
      reload();
    } catch {
      setActionError(
        `“${entry.title}” could not be deleted. Please try again.`,
      );
      setDeleting(null);
    } finally {
      setBusyEntryId(null);
    }
  }

  const counts = data?.category_counts;
  const allCount = counts
    ? Object.values(counts).reduce((sum, value) => sum + value, 0)
    : 0;
  const filtered = Boolean(search || category || status === "ARCHIVED");

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Knowledge"
        description="Facts about your business that the AI may use when it drafts replies: FAQs, products and pricing, policies, and company details."
        primaryAction={
          canManage ? (
            <Button type="button" onClick={() => openDialog(null)}>
              <Plus aria-hidden="true" />
              Add entry
            </Button>
          ) : (
            <span className="text-muted-foreground text-xs">
              Only owners and admins can add or change knowledge.
            </span>
          )
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="How the AI uses knowledge"
          description="When the AI drafts a reply, it reads the active entries that best match the customer's message. It is told to state pricing, features, or policies only when they appear here. Nothing is sent until a person approves the draft. Archived entries and entries with AI use turned off are never used."
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Entries"
          description={
            data
              ? `${data.total.toLocaleString()} ${status === "ARCHIVED" ? "archived" : "active"} ${data.total === 1 ? "entry" : "entries"} shown.`
              : "Search, filter, and manage your knowledge entries."
          }
        />
        <FilterBar className="!grid grid-cols-1 gap-3 sm:grid-cols-3">
          <SearchInput
            id="knowledge-search"
            label="Search knowledge"
            placeholder="Search titles and content"
            value={query}
            onChange={(event) => {
              setLoading(true);
              setQuery(event.target.value);
            }}
            onClear={() => {
              setLoading(true);
              setQuery("");
            }}
            className="sm:max-w-none"
          />
          <div>
            <label htmlFor="knowledge-category-filter" className="sr-only">
              Category
            </label>
            <Select
              id="knowledge-category-filter"
              value={category ?? "all"}
              onChange={(event) => {
                setLoading(true);
                setCategory(
                  event.target.value === "all"
                    ? null
                    : (event.target.value as KnowledgeCategory),
                );
              }}
            >
              <option value="all">All categories ({allCount})</option>
              {Object.entries(knowledgeCategoryLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label} ({counts?.[value as KnowledgeCategory] ?? 0})
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label htmlFor="knowledge-status-filter" className="sr-only">
              Status
            </label>
            <Select
              id="knowledge-status-filter"
              value={status}
              onChange={(event) => {
                setLoading(true);
                setStatus(event.target.value as KnowledgeEntryStatus);
              }}
            >
              <option value="ACTIVE">Active</option>
              <option value="ARCHIVED">Archived</option>
            </Select>
          </div>
        </FilterBar>

        {actionError ? (
          <p className="text-danger-text text-sm" role="alert">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <div className="grid gap-3" role="status">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <span className="sr-only">Loading knowledge</span>
          </div>
        ) : error ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Knowledge could not be loaded"
            description="Check your connection and try again."
            action={
              <Button type="button" onClick={reload}>
                Retry
              </Button>
            }
          />
        ) : data && data.items.length > 0 ? (
          <KnowledgeEntryList
            entries={data.items}
            canManage={canManage}
            busyEntryId={busyEntryId}
            onEdit={(entry) => openDialog(entry)}
            onToggleArchive={(entry) => void toggleArchive(entry)}
            onDelete={setDeleting}
          />
        ) : filtered ? (
          <EmptyState
            compact
            headingLevel={3}
            title="No matching entries"
            description="Try a different search, category, or status."
          />
        ) : (
          <EmptyState
            headingLevel={3}
            icon={<BookOpen />}
            title="Add your first knowledge entry"
            description="Start with the questions customers ask most, your pricing, and your refund policy. The AI uses these facts instead of guessing."
            action={
              canManage ? (
                <Button type="button" onClick={() => openDialog(null)}>
                  <Plus aria-hidden="true" />
                  Add entry
                </Button>
              ) : undefined
            }
          />
        )}
      </section>

      <KnowledgeEntryDialog
        key={`knowledge-dialog-${dialogKey}`}
        open={dialogOpen}
        entry={editing}
        onOpenChange={setDialogOpen}
        onSaved={() => reload()}
      />
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open) setDeleting(null);
        }}
        title="Delete this entry?"
        description={`“${deleting?.title ?? ""}” will be removed permanently and the AI will stop using it. To keep it for later, archive it instead.`}
        confirmLabel="Delete entry"
        variant="destructive"
        confirmPending={deleting !== null && busyEntryId === deleting.id}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
