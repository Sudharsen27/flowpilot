"use client";

import { Plus, Target } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { DealFormDialog } from "@/components/deals/deal-form-dialog";
import { DealsTable } from "@/components/deals/deals-table";
import { DealsToolbar } from "@/components/deals/deals-toolbar";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { listDeals } from "@/lib/api/deals";
import { getLead } from "@/lib/api/leads";
import { getCurrentOrganization, listOrganizationMembers } from "@/lib/api/organizations";
import {
  DEALS_PAGE_SIZE,
  type DealsUrlState,
  hasDealFilters,
  parseDealsSearchParams,
  serializeDealsSearchParams,
} from "@/lib/deals-url";
import type { DealListResponse, MemberPublic } from "@/types/api";

type LoadResult =
  | { key: string; page: DealListResponse; failed: false }
  | { key: string; page: null; failed: true };

export function DealsWorkspace() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const toast = useToast();
  // Read through a ref: the toast API changes identity whenever a toast appears,
  // and must not re-run the lead lookup (which could toast again, forever).
  const toastRef = useRef(toast);
  useEffect(() => {
    toastRef.current = toast;
  }, [toast]);
  const { session } = useAuth();
  const urlState = useMemo(() => parseDealsSearchParams(searchParams), [searchParams]);

  const [retryKey, setRetryKey] = useState(0);
  const listKey = `${serializeDealsSearchParams({ ...urlState, create: false, leadId: null })}#${retryKey}`;
  const [result, setResult] = useState<LoadResult | null>(null);
  const [members, setMembers] = useState<MemberPublic[]>([]);
  const [currency, setCurrency] = useState<string | null>(
    session?.organization.default_currency ?? null,
  );
  const [queryInput, setQueryInput] = useState(urlState.q);
  const [trackedQuery, setTrackedQuery] = useState(urlState.q);
  // Lead requested by `?lead_id=`; `lead` stays null when it could not be loaded.
  const [prefill, setPrefill] = useState<{
    leadId: string;
    lead: { id: string; name: string } | null;
  } | null>(null);
  const [formKey, setFormKey] = useState(0);

  if (urlState.q !== trackedQuery) {
    setTrackedQuery(urlState.q);
    setQueryInput(urlState.q);
  }

  const isLoading = result?.key !== listKey;
  const page = !isLoading && result ? result.page : null;
  const failed = !isLoading && result ? result.failed : false;
  const rangeInvalid = Boolean(
    urlState.closeDateFrom && urlState.closeDateTo && urlState.closeDateFrom > urlState.closeDateTo,
  );

  const replaceUrl = useCallback(
    (next: DealsUrlState) => {
      const serialized = serializeDealsSearchParams(next);
      if (serialized === searchParams.toString()) return;
      router.replace(serialized ? `${pathname}?${serialized}` : pathname, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  function patchFilters(patch: Partial<DealsUrlState>) {
    replaceUrl({ ...urlState, offset: 0, ...patch });
  }

  useEffect(() => {
    let cancelled = false;
    void Promise.allSettled([getCurrentOrganization(), listOrganizationMembers()]).then(
      ([organization, memberList]) => {
        if (cancelled) return;
        if (organization.status === "fulfilled" && organization.value.default_currency) {
          setCurrency(organization.value.default_currency);
        }
        if (memberList.status === "fulfilled") setMembers(memberList.value);
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (rangeInvalid) return;
    let cancelled = false;
    void listDeals({
      q: urlState.q || undefined,
      stage: urlState.stage ?? undefined,
      ownerUserId: urlState.ownerUserId ?? undefined,
      closeDateFrom: urlState.closeDateFrom ?? undefined,
      closeDateTo: urlState.closeDateTo ?? undefined,
      limit: DEALS_PAGE_SIZE,
      offset: urlState.offset,
    })
      .then((data) => {
        if (!cancelled) setResult({ key: listKey, page: data, failed: false });
      })
      .catch(() => {
        if (!cancelled) setResult({ key: listKey, page: null, failed: true });
      });
    return () => {
      cancelled = true;
    };
  }, [
    listKey,
    rangeInvalid,
    urlState.closeDateFrom,
    urlState.closeDateTo,
    urlState.offset,
    urlState.ownerUserId,
    urlState.q,
    urlState.stage,
  ]);

  // Debounce typing into the URL so each keystroke does not refetch.
  useEffect(() => {
    const handle = window.setTimeout(() => {
      const trimmed = queryInput.trim();
      if (trimmed !== urlState.q) replaceUrl({ ...urlState, offset: 0, q: trimmed });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [queryInput, replaceUrl, urlState]);

  // `?create=1&lead_id=…` (e.g. from a lead page) opens the form for that lead.
  useEffect(() => {
    const leadId = urlState.leadId;
    if (!urlState.create || !leadId) return;
    let cancelled = false;
    void getLead(leadId)
      .then((lead) => {
        if (!cancelled) setPrefill({ leadId, lead: { id: lead.id, name: lead.name } });
      })
      .catch(() => {
        if (cancelled) return;
        setPrefill({ leadId, lead: null });
        toastRef.current.error({
          title: "Lead not available",
          description: "That lead could not be found, so the deal will not be linked to it.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [urlState.create, urlState.leadId]);

  function openCreate() {
    setFormKey((key) => key + 1);
    replaceUrl({ ...urlState, create: true, leadId: null });
  }

  function closeCreate() {
    setPrefill(null);
    replaceUrl({ ...urlState, create: false, leadId: null });
  }

  const total = page?.total ?? 0;
  const items = page?.items ?? [];
  const start = total === 0 ? 0 : urlState.offset + 1;
  const end = Math.min(urlState.offset + DEALS_PAGE_SIZE, total);
  const filtered = hasDealFilters(urlState);
  const waitingForLead =
    urlState.create && Boolean(urlState.leadId) && prefill?.leadId !== urlState.leadId;
  const prefillLead = prefill?.leadId === urlState.leadId ? prefill.lead : null;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Deals"
        description={
          page
            ? `${total} ${total === 1 ? "deal" : "deals"}${filtered ? " match these filters" : " in your pipeline"}.`
            : "Revenue opportunities across your organization."
        }
        secondaryActions={
          <Link href="/deals/targets" className={buttonVariants({ variant: "outline" })}>
            <Target aria-hidden="true" />
            Sales targets
          </Link>
        }
        primaryAction={
          <Button type="button" onClick={openCreate}>
            <Plus aria-hidden="true" />
            Create deal
          </Button>
        }
      />

      <section className="grid gap-4" aria-label="Deals list">
        <DealsToolbar
          query={queryInput}
          stage={urlState.stage}
          ownerUserId={urlState.ownerUserId}
          closeDateFrom={urlState.closeDateFrom}
          closeDateTo={urlState.closeDateTo}
          members={members}
          onQueryChange={setQueryInput}
          onStageChange={(stage) => patchFilters({ stage })}
          onOwnerChange={(ownerUserId) => patchFilters({ ownerUserId })}
          onCloseDateFromChange={(closeDateFrom) => patchFilters({ closeDateFrom })}
          onCloseDateToChange={(closeDateTo) => patchFilters({ closeDateTo })}
          onClearFilters={() => {
            setQueryInput("");
            patchFilters({
              q: "",
              stage: null,
              ownerUserId: null,
              closeDateFrom: null,
              closeDateTo: null,
            });
          }}
        />

        {rangeInvalid ? null : failed ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            headingLevel={3}
            title="Deals could not be loaded"
            description="Check your connection and try again."
            action={
              <Button type="button" onClick={() => setRetryKey((key) => key + 1)}>
                Retry
              </Button>
            }
          />
        ) : !isLoading && items.length === 0 && filtered ? (
          <StatePanel
            className="max-w-none"
            headingLevel={3}
            title="No deals match these filters"
            description="Try a different search, stage, owner or close date range."
            action={
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setQueryInput("");
                  patchFilters({
                    q: "",
                    stage: null,
                    ownerUserId: null,
                    closeDateFrom: null,
                    closeDateTo: null,
                  });
                }}
              >
                Clear filters
              </Button>
            }
          />
        ) : (
          <>
            <DealsTable deals={items} loading={isLoading} />
            {!isLoading && total > 0 ? (
              <nav
                className="flex flex-wrap items-center justify-between gap-3"
                aria-label="Deals pagination"
              >
                <p className="text-muted-foreground text-sm" aria-live="polite">
                  Showing {start}–{end} of {total}
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={urlState.offset === 0}
                    aria-label="Previous deals page"
                    onClick={() =>
                      replaceUrl({
                        ...urlState,
                        offset: Math.max(0, urlState.offset - DEALS_PAGE_SIZE),
                      })
                    }
                  >
                    Previous
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={urlState.offset + DEALS_PAGE_SIZE >= total}
                    aria-label="Next deals page"
                    onClick={() =>
                      replaceUrl({ ...urlState, offset: urlState.offset + DEALS_PAGE_SIZE })
                    }
                  >
                    Next
                  </Button>
                </div>
              </nav>
            ) : null}
          </>
        )}
      </section>

      {urlState.create && !waitingForLead ? (
        <DealFormDialog
          key={`create-${formKey}-${prefillLead?.id ?? "none"}`}
          open
          onOpenChange={(open) => {
            if (!open) closeCreate();
          }}
          currency={currency}
          members={members}
          currentUserId={session?.user.id}
          role={session?.membership.role}
          initialLead={prefillLead}
          onSaved={(deal) => {
            toast.success({
              title: "Deal created",
              description: deal.lead_name
                ? `${deal.name} was created and ${deal.lead_name} is now converted.`
                : `${deal.name} was added to your pipeline.`,
            });
            setRetryKey((key) => key + 1);
          }}
        />
      ) : null}
    </div>
  );
}
