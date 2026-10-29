"use client";

import { ArrowRightLeft, Pencil, Receipt } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { DealAmountCorrectionDialog } from "@/components/deals/deal-amount-correction-dialog";
import { DealFormDialog } from "@/components/deals/deal-form-dialog";
import { DealHistoryList } from "@/components/deals/deal-history";
import { DealProbability, DealStageBadge } from "@/components/deals/deal-stage-badge";
import { ForecastCategoryBadge } from "@/components/deals/forecast-category-badge";
import { DealStageDialog } from "@/components/deals/deal-stage-dialog";
import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { RelativeTime } from "@/components/ui/relative-time";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { getDeal, getDealHistory } from "@/lib/api/deals";
import { listOrganizationMembers } from "@/lib/api/organizations";
import { WON_STAGE_LOCKED_MESSAGE, canChangeStage, canCorrectWonAmount } from "@/lib/deals";
import { buildLeadHref } from "@/lib/lead-url";
import { formatDateOnly, formatMoney } from "@/lib/money";
import type { Deal, DealHistoryResponse, MemberPublic } from "@/types/api";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; deal: Deal }
  | { status: "not-found" }
  | { status: "error" };

export default function DealDetailPage() {
  const params = useParams<{ id: string }>();
  const dealId = params.id;
  const { session } = useAuth();
  const toast = useToast();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [retryKey, setRetryKey] = useState(0);
  const [history, setHistory] = useState<DealHistoryResponse | null>(null);
  const [historyFailed, setHistoryFailed] = useState(false);
  const [historyKey, setHistoryKey] = useState(0);
  const [members, setMembers] = useState<MemberPublic[]>([]);
  const [editOpen, setEditOpen] = useState(false);
  const [stageOpen, setStageOpen] = useState(false);
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [dialogKey, setDialogKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getDeal(dealId)
      .then((deal) => {
        if (!cancelled) setState({ status: "ready", deal });
      })
      .catch((cause: unknown) => {
        if (cancelled) return;
        setState({
          status: cause instanceof ApiError && cause.status === 404 ? "not-found" : "error",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [dealId, retryKey]);

  useEffect(() => {
    let cancelled = false;
    void getDealHistory(dealId, { limit: 200 })
      .then((data) => {
        if (cancelled) return;
        setHistory(data);
        setHistoryFailed(false);
      })
      .catch(() => {
        if (!cancelled) setHistoryFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [dealId, historyKey]);

  useEffect(() => {
    let cancelled = false;
    void listOrganizationMembers()
      .then((data) => {
        if (!cancelled) setMembers(data);
      })
      .catch(() => {
        if (!cancelled) setMembers([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const reload = useCallback(async () => {
    try {
      const latest = await getDeal(dealId);
      setState({ status: "ready", deal: latest });
      setHistoryKey((key) => key + 1);
      return latest;
    } catch {
      return null;
    }
  }, [dealId]);

  function applySaved(deal: Deal, message: string) {
    setState({ status: "ready", deal });
    setHistoryKey((key) => key + 1);
    toast.success({ title: message, description: deal.name });
  }

  if (state.status === "loading") {
    return (
      <div className="gap-section flex flex-col" aria-busy="true">
        <PageHeader
          breadcrumbs={[{ label: "Deals", href: "/deals" }, { label: "Loading" }]}
          title="Loading deal"
        />
        <Card className="grid gap-4 p-5" role="status">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-24 w-full" />
          <span className="sr-only">Loading deal</span>
        </Card>
      </div>
    );
  }

  if (state.status !== "ready") {
    const notFound = state.status === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[
            { label: "Deals", href: "/deals" },
            { label: notFound ? "Not found" : "Unavailable" },
          ]}
          title={notFound ? "Deal not found" : "Deal unavailable"}
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={notFound ? "This deal could not be found." : "Unable to load this deal"}
          description={
            notFound
              ? "It may not exist or may belong to another organization."
              : "Check your connection and try again."
          }
          action={
            <div className="flex flex-wrap gap-2">
              {!notFound ? (
                <Button
                  type="button"
                  onClick={() => {
                    setState({ status: "loading" });
                    setRetryKey((key) => key + 1);
                  }}
                >
                  Retry
                </Button>
              ) : null}
              <Link href="/deals" className={buttonVariants({ variant: "outline" })}>
                Back to Deals
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  const deal = state.deal;
  const leadHref = deal.lead_id ? buildLeadHref(deal.lead_id) : null;
  const role = session?.membership.role;
  // The API enforces both rules; hiding the controls just avoids offering a dead end.
  const stageChangeAllowed = canChangeStage(deal, role);
  const correctionAllowed = canCorrectWonAmount(deal, role);

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[{ label: "Deals", href: "/deals" }, { label: deal.name }]}
        title={deal.name}
        titleBadge={<DealStageBadge stage={deal.stage} />}
        description={`${formatMoney(deal.amount, deal.currency)} · expected to close ${formatDateOnly(deal.expected_close_date)}`}
        secondaryActions={
          <>
            {correctionAllowed ? (
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setDialogKey((key) => key + 1);
                  setCorrectionOpen(true);
                }}
              >
                <Receipt aria-hidden="true" />
                Correct amount
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setDialogKey((key) => key + 1);
                setEditOpen(true);
              }}
            >
              <Pencil aria-hidden="true" />
              Edit
            </Button>
          </>
        }
        primaryAction={
          stageChangeAllowed ? (
            <Button
              type="button"
              onClick={() => {
                setDialogKey((key) => key + 1);
                setStageOpen(true);
              }}
            >
              <ArrowRightLeft aria-hidden="true" />
              Change stage
            </Button>
          ) : undefined
        }
      />

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card as="section" className="grid content-start gap-5 p-4 sm:p-5" aria-labelledby="deal-details-title">
          <h2 id="deal-details-title" className="text-section-title font-semibold tracking-tight">
            Deal details
          </h2>
          <dl className="grid gap-4 sm:grid-cols-2">
            <DetailRow label="Amount" value={formatMoney(deal.amount, deal.currency)} />
            <DetailRow label="Currency" value={deal.currency} />
            <DetailRow label="Stage" value={<DealStageBadge stage={deal.stage} />} />
            <DetailRow label="Probability" value={<DealProbability deal={deal} />} />
            <DetailRow
              label="Forecast category"
              value={<ForecastCategoryBadge stage={deal.stage} category={deal.forecast_category} />}
            />
            <DetailRow label="Expected close" value={formatDateOnly(deal.expected_close_date)} />
            <DetailRow
              label="Closed"
              value={deal.closed_at ? <RelativeTime value={deal.closed_at} /> : "Open"}
              muted={!deal.closed_at}
            />
            <DetailRow
              label="Owner"
              value={deal.owner_name ?? "Unassigned"}
              muted={!deal.owner_name}
            />
            <DetailRow
              label="Lead"
              value={
                leadHref && deal.lead_name ? (
                  <Link href={leadHref} className="underline-offset-4 hover:underline">
                    {deal.lead_name}
                  </Link>
                ) : deal.lead_id ? (
                  "Lead unavailable"
                ) : (
                  "Not linked"
                )
              }
              muted={!deal.lead_name}
            />
            {deal.stage === "CLOSED_LOST" ? (
              <div className="sm:col-span-2">
                <DetailRow label="Lost reason" value={deal.lost_reason ?? "—"} />
              </div>
            ) : null}
            <DetailRow label="In stage since" value={<RelativeTime value={deal.stage_entered_at} />} />
            <DetailRow label="Last updated" value={<RelativeTime value={deal.updated_at} />} />
            <DetailRow label="Created" value={<RelativeTime value={deal.created_at} />} />
            <DetailRow label="Revision" value={`#${deal.revision}`} muted />
          </dl>
          {stageChangeAllowed ? null : (
            <p
              className="border-border bg-surface-subtle rounded-md border px-3 py-2 text-sm"
              role="note"
            >
              {WON_STAGE_LOCKED_MESSAGE}
            </p>
          )}
          {deal.description ? (
            <div className="grid gap-1">
              <h3 className="text-muted-foreground text-xs font-medium">Description</h3>
              <p className="text-sm leading-6 whitespace-pre-line">{deal.description}</p>
            </div>
          ) : null}
        </Card>

        <Card as="section" className="grid content-start gap-4 p-4 sm:p-5" aria-labelledby="deal-history-title">
          <div>
            <h2 id="deal-history-title" className="text-section-title font-semibold tracking-tight">
              History
            </h2>
            <p className="text-muted-foreground mt-1 text-sm">
              Stage, amount, close-date, probability and forecast category changes, oldest first.
            </p>
          </div>
          {historyFailed ? (
            <StatePanel
              kind="error"
              className="max-w-none"
              headingLevel={3}
              title="History could not be loaded"
              description="The deal details above are still current."
              action={
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setHistoryKey((key) => key + 1)}
                >
                  Retry history
                </Button>
              }
            />
          ) : history ? (
            <DealHistoryList events={history.items} currency={deal.currency} />
          ) : (
            <div role="status" className="grid gap-2">
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
              <span className="sr-only">Loading history</span>
            </div>
          )}
        </Card>
      </div>

      {editOpen ? (
        <DealFormDialog
          key={`edit-${dialogKey}`}
          open
          onOpenChange={setEditOpen}
          deal={deal}
          currency={deal.currency}
          members={members}
          currentUserId={session?.user.id}
          role={role}
          onSaved={(saved) => applySaved(saved, "Deal updated")}
          onReload={reload}
        />
      ) : null}
      {stageOpen ? (
        <DealStageDialog
          key={`stage-${dialogKey}`}
          open
          onOpenChange={setStageOpen}
          deal={deal}
          role={role}
          onSaved={(saved) => applySaved(saved, "Stage changed")}
          onReload={reload}
        />
      ) : null}
      {correctionOpen ? (
        <DealAmountCorrectionDialog
          key={`correction-${dialogKey}`}
          open
          onOpenChange={setCorrectionOpen}
          deal={deal}
          onSaved={(saved) => applySaved(saved, "Amount corrected")}
          onReload={reload}
        />
      ) : null}
    </div>
  );
}
