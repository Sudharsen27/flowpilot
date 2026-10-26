"use client";

import { Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { CompanyProspectCreateDialog } from "@/components/company-prospects/company-prospect-create-dialog";
import { CompanyProspectsTable } from "@/components/company-prospects/company-prospects-table";
import { CompanyProspectsToolbar } from "@/components/company-prospects/company-prospects-toolbar";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { getCompanyProspects } from "@/lib/api/company-prospects";
import type {
  CompanyProspectListResponse,
  CompanyProspectStatus,
} from "@/types/api";

const PAGE_SIZE = 20;

export default function CompanyProspectsPage() {
  const { session } = useAuth();
  const role = session?.membership.role;
  const canManage = role === "OWNER" || role === "ADMIN";

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<CompanyProspectStatus | "">("");
  const [offset, setOffset] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [page, setPage] = useState<CompanyProspectListResponse | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getCompanyProspects({
      q: query.trim() || undefined,
      status: status || undefined,
      limit: PAGE_SIZE,
      offset,
    })
      .then((data) => {
        if (!cancelled) setPage(data);
      })
      .catch(() => {
        if (!cancelled) {
          setHasError(true);
          setPage(null);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [offset, query, retryKey, status]);

  function beginFetch() {
    setIsLoading(true);
    setHasError(false);
  }

  function clearFilters() {
    beginFetch();
    setQuery("");
    setStatus("");
    setOffset(0);
  }

  const total = page?.total ?? 0;
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + PAGE_SIZE, total);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Company Prospects"
        description="Browse and manage companies saved in this organization."
        primaryAction={
          canManage ? (
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add company prospect
            </Button>
          ) : undefined
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Company directory"
          description="Search saved company names and website domains, then open a record for its stored evidence and lifecycle status."
        />
        <CompanyProspectsToolbar
          query={query}
          status={status}
          onQueryChange={(value) => {
            beginFetch();
            setQuery(value);
            setOffset(0);
          }}
          onStatusChange={(value) => {
            beginFetch();
            setStatus(value);
            setOffset(0);
          }}
          onClearFilters={clearFilters}
        />
        {hasError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Company prospects could not be loaded"
            description="The company directory is unavailable right now. Retry to load this organization's records."
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
        ) : (
          <>
            <CompanyProspectsTable
              prospects={page?.items ?? []}
              loading={isLoading}
            />
            {total > 0 ? (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-muted-foreground text-sm">
                  Showing {start}–{end} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={offset === 0 || isLoading}
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
                    disabled={offset + PAGE_SIZE >= total || isLoading}
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
          </>
        )}
      </section>

      <CompanyProspectCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
      />
    </div>
  );
}
