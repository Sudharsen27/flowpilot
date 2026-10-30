"use client";

import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { SalesTargetDialog, monthStarts } from "@/components/deals/sales-target-dialog";
import { DataTable, type DataTableColumn } from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { getCurrentOrganization, listOrganizationMembers } from "@/lib/api/organizations";
import { listSalesTargets } from "@/lib/api/sales-targets";
import { canManageDeals } from "@/lib/deals";
import { formatMoney, formatMonth } from "@/lib/money";
import { parseSalesTargetsYear } from "@/lib/sales-targets";
import type { MemberPublic, SalesTarget } from "@/types/api";

type MonthRow = { periodStart: string; target: SalesTarget | null };
type DialogState = { key: number; initial: { periodStart: string; ownerUserId: string | null } | null };

function SalesTargetsFallback() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-12 w-48" />
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading sales targets</span>
    </div>
  );
}

export default function SalesTargetsPage() {
  return (
    <Suspense fallback={<SalesTargetsFallback />}>
      <SalesTargetsWorkspace />
    </Suspense>
  );
}

function SalesTargetsWorkspace() {
  const { session } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const canManage = canManageDeals(session?.membership.role);
  const [currentYear] = useState(() => new Date().getFullYear());
  // The year lives in the URL (?year=YYYY) so links, such as the forecast's "Set
  // targets", open the right year; the current year is the canonical plain URL.
  const year = parseSalesTargetsYear(searchParams, currentYear);
  const [targets, setTargets] = useState<SalesTarget[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [loadedYear, setLoadedYear] = useState<number | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [members, setMembers] = useState<MemberPublic[]>([]);
  const [currency, setCurrency] = useState<string | null>(
    session?.organization.default_currency ?? null,
  );
  const [dialog, setDialog] = useState<DialogState | null>(null);

  const loading = loadedYear !== year;

  useEffect(() => {
    let cancelled = false;
    void listSalesTargets({
      periodFrom: `${year}-01-01`,
      periodTo: `${year}-12-01`,
      limit: 200,
    })
      .then((page) => {
        if (cancelled) return;
        setTargets(page.items);
        setFailed(false);
        setLoadedYear(year);
      })
      .catch(() => {
        if (cancelled) return;
        setTargets(null);
        setFailed(true);
        setLoadedYear(year);
      });
    return () => {
      cancelled = true;
    };
  }, [retryKey, year]);

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

  const items = targets ?? [];
  const monthRows: MonthRow[] = monthStarts(year).map((periodStart) => ({
    periodStart,
    target:
      items.find((item) => item.period_start === periodStart && item.owner_user_id === null) ??
      null,
  }));
  const ownerTargets = items.filter((item) => item.owner_user_id !== null);

  function changeYear(next: number) {
    const query = new URLSearchParams(searchParams);
    if (next === currentYear) query.delete("year");
    else query.set("year", String(next));
    const serialized = query.toString();
    router.replace(serialized ? `${pathname}?${serialized}` : pathname, { scroll: false });
  }

  function openDialog(initial: DialogState["initial"]) {
    setDialog((current) => ({ key: (current?.key ?? 0) + 1, initial }));
  }

  const monthColumns: DataTableColumn<MonthRow>[] = [
    { key: "month", header: "Month", cell: (row) => formatMonth(row.periodStart) },
    {
      key: "amount",
      header: "Organization target",
      cell: (row) =>
        row.target ? (
          <span className="tabular-nums">{formatMoney(row.target.amount, row.target.currency)}</span>
        ) : (
          <span className="text-muted-foreground">Not set</span>
        ),
      className: "text-right whitespace-nowrap",
    },
    {
      key: "updated",
      header: "Last updated",
      cell: (row) =>
        row.target ? <RelativeTime value={row.target.updated_at} /> : <span className="text-muted-foreground">—</span>,
    },
  ];

  const ownerColumns: DataTableColumn<SalesTarget>[] = [
    { key: "owner", header: "Owner", cell: (row) => row.owner_name ?? "Former member" },
    { key: "month", header: "Month", cell: (row) => formatMonth(row.period_start) },
    {
      key: "amount",
      header: "Target",
      cell: (row) => <span className="tabular-nums">{formatMoney(row.amount, row.currency)}</span>,
      className: "text-right whitespace-nowrap",
    },
  ];

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[{ label: "Deals", href: "/deals" }, { label: "Sales targets" }]}
        title="Sales targets"
        description={`Monthly revenue targets${currency ? ` in ${currency}` : ""}. Targets are goals, not forecasts.`}
        primaryAction={
          canManage ? (
            <Button type="button" onClick={() => openDialog(null)}>
              <Plus aria-hidden="true" />
              Set target
            </Button>
          ) : undefined
        }
      />

      {!canManage ? (
        <p className="text-muted-foreground text-sm" role="note">
          You can view targets. Only owners and admins can set or change them.
        </p>
      ) : null}

      <div className="flex items-center gap-2" role="group" aria-label="Target year">
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Previous year"
          onClick={() => changeYear(year - 1)}
        >
          <ChevronLeft aria-hidden="true" />
        </Button>
        <span className="min-w-16 text-center text-sm font-medium tabular-nums" aria-live="polite">
          {year}
        </span>
        <Button
          type="button"
          variant="outline"
          size="icon"
          aria-label="Next year"
          onClick={() => changeYear(year + 1)}
        >
          <ChevronRight aria-hidden="true" />
        </Button>
      </div>

      {failed && !loading ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          title="Sales targets could not be loaded"
          description="Check your connection and try again."
          action={
            <Button
              type="button"
              onClick={() => {
                setLoadedYear(null);
                setRetryKey((key) => key + 1);
              }}
            >
              Retry
            </Button>
          }
        />
      ) : (
        <>
          <section className="grid gap-4" aria-labelledby="organization-targets-title">
            <SectionHeader
              id="organization-targets-title"
              title="Organization targets"
              description="One target per calendar month for the whole organization."
            />
            <DataTable
              columns={monthColumns}
              rows={monthRows}
              loading={loading}
              getRowKey={(row) => row.periodStart}
              headingLevel={3}
              rowActions={
                canManage
                  ? (row) => (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-label={`${row.target ? "Edit" : "Set"} target for ${formatMonth(row.periodStart)}`}
                        onClick={() => openDialog({ periodStart: row.periodStart, ownerUserId: null })}
                      >
                        {row.target ? "Edit" : "Set"}
                      </Button>
                    )
                  : undefined
              }
            />
          </section>

          <section className="grid gap-4" aria-labelledby="owner-targets-title">
            <SectionHeader
              id="owner-targets-title"
              title="Owner targets"
              description="Optional targets for individual deal owners."
            />
            <DataTable
              columns={ownerColumns}
              rows={ownerTargets}
              loading={loading}
              getRowKey={(row) => row.id}
              headingLevel={3}
              emptyTitle={`No owner targets for ${year}`}
              emptyDescription={
                canManage
                  ? "Use Set target and choose an owner to add one."
                  : "Owners and admins can add targets for individual owners."
              }
              rowActions={
                canManage
                  ? (row) => (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-label={`Edit ${row.owner_name ?? "owner"} target for ${formatMonth(row.period_start)}`}
                        onClick={() =>
                          openDialog({ periodStart: row.period_start, ownerUserId: row.owner_user_id })
                        }
                      >
                        Edit
                      </Button>
                    )
                  : undefined
              }
            />
          </section>
        </>
      )}

      {dialog && canManage ? (
        <SalesTargetDialog
          key={dialog.key}
          open
          onOpenChange={(open) => {
            if (!open) setDialog(null);
          }}
          year={year}
          currency={currency}
          members={members}
          targets={items}
          initial={dialog.initial}
          onSaved={(target, created) => {
            toast.success({
              title: created ? "Target set" : "Target updated",
              description: `${formatMonth(target.period_start)}: ${formatMoney(target.amount, target.currency)}`,
            });
            setRetryKey((key) => key + 1);
          }}
        />
      ) : null}
    </div>
  );
}
