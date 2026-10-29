"use client";

import { Lock, MoreHorizontal } from "lucide-react";
import Link from "next/link";
import { type DragEvent, useCallback, useEffect, useState } from "react";

import { DealDrawer } from "@/components/deals/deal-drawer";
import { DealProbability } from "@/components/deals/deal-stage-badge";
import { ForecastCategoryBadge } from "@/components/deals/forecast-category-badge";
import { DealStageDialog } from "@/components/deals/deal-stage-dialog";
import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import {
  changeDealStage,
  forbiddenMessage,
  getDeal,
  isRevisionConflict,
  listDeals,
} from "@/lib/api/deals";
import { getPipelineSummary } from "@/lib/api/pipeline";
import {
  DEAL_STAGES,
  DEAL_STAGE_LABELS,
  WON_STAGE_LOCKED_MESSAGE,
  canChangeStage,
  canManageDeals,
  forecastCategoryAfterMove,
  isClosedStage,
} from "@/lib/deals";
import { DEALS_PATH } from "@/lib/deals-url";
import { formatDateOnly, formatMoney, formatMoneyCompact } from "@/lib/money";
import { cn } from "@/lib/utils";
import type { Deal, DealStage, PipelineSummary } from "@/types/api";

/** Cards shown per column; larger columns link to the filtered list. */
export const BOARD_COLUMN_LIMIT = 50;
const DRAG_TYPE = "application/x-flowpilot-deal";

type Column = { items: Deal[]; total: number };
type BoardState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; columns: Record<DealStage, Column> };

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function loadColumns(): Promise<Record<DealStage, Column>> {
  const pages = await Promise.all(
    DEAL_STAGES.map((stage) => listDeals({ stage, limit: BOARD_COLUMN_LIMIT })),
  );
  return Object.fromEntries(
    DEAL_STAGES.map((stage, index) => [
      stage,
      { items: pages[index]!.items, total: pages[index]!.total },
    ]),
  ) as Record<DealStage, Column>;
}

function DealCard({
  deal,
  onOpen,
  onMove,
  moving,
  locked,
}: {
  deal: Deal;
  onOpen: (deal: Deal) => void;
  onMove: (deal: Deal, stage: DealStage) => void;
  moving: boolean;
  /** The viewer may not move this deal (a won deal, for members). */
  locked: boolean;
}) {
  const overdue =
    !isClosedStage(deal.stage) && deal.expected_close_date < todayIso();
  return (
    <li
      draggable={!moving && !locked}
      onDragStart={(event) => {
        if (locked) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData(DRAG_TYPE, deal.id);
        event.dataTransfer.effectAllowed = "move";
      }}
      aria-busy={moving || undefined}
      className={cn(
        "border-border bg-card shadow-card group hover:shadow-raised grid gap-2 rounded-lg border p-3 transition-shadow",
        moving && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <button
          type="button"
          onClick={() => onOpen(deal)}
          className="focus-visible:ring-ring min-w-0 rounded-sm text-left text-sm font-medium outline-none hover:underline focus-visible:ring-2"
        >
          {deal.name}
        </button>
        {locked ? (
          <span
            role="img"
            aria-label={WON_STAGE_LOCKED_MESSAGE}
            title={WON_STAGE_LOCKED_MESSAGE}
            className="text-muted-foreground inline-flex size-6 shrink-0 items-center justify-center"
          >
            <Lock aria-hidden="true" className="size-3.5" />
          </span>
        ) : (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={`Move ${deal.name}`}
                  disabled={moving}
                />
              }
            >
              <MoreHorizontal aria-hidden="true" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-44">
              <DropdownMenuGroup>
                <DropdownMenuLabel>Move to</DropdownMenuLabel>
                {DEAL_STAGES.filter((stage) => stage !== deal.stage).map(
                  (stage) => (
                    <DropdownMenuItem
                      key={stage}
                      onClick={() => onMove(deal, stage)}
                    >
                      {DEAL_STAGE_LABELS[stage]}
                    </DropdownMenuItem>
                  ),
                )}
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-base font-semibold tracking-tight tabular-nums">
          {formatMoney(deal.amount, deal.currency)}
        </p>
        {isClosedStage(deal.stage) ? null : (
          <ForecastCategoryBadge stage={deal.stage} category={deal.forecast_category} />
        )}
      </div>
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span>{deal.owner_name ?? "Unassigned"}</span>
        <span aria-hidden="true">·</span>
        <span className={overdue ? "text-warning-text font-medium" : undefined}>
          {overdue ? "Overdue · " : "Closes "}
          {formatDateOnly(deal.expected_close_date)}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="text-muted-foreground truncate">
          {deal.lead_name ?? "No linked lead"}
        </span>
        {isClosedStage(deal.stage) ? null : <DealProbability deal={deal} />}
      </div>
      {overdue ? (
        <span className="sr-only">
          This deal is past its expected close date.
        </span>
      ) : null}
    </li>
  );
}

export function PipelineBoard() {
  const toast = useToast();
  const { session } = useAuth();
  const role = session?.membership.role;
  const [board, setBoard] = useState<BoardState>({ status: "loading" });
  const [summary, setSummary] = useState<PipelineSummary | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [moving, setMoving] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<DealStage | null>(null);
  const [drawerDeal, setDrawerDeal] = useState<Deal | null>(null);
  const [closing, setClosing] = useState<{
    deal: Deal;
    stage: DealStage;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.allSettled([loadColumns(), getPipelineSummary(1)]).then(
      ([columns, totals]) => {
        if (cancelled) return;
        setBoard(
          columns.status === "fulfilled"
            ? { status: "ready", columns: columns.value }
            : { status: "error" },
        );
        setSummary(totals.status === "fulfilled" ? totals.value : null);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);

  function findDeal(dealId: string): Deal | null {
    if (board.status !== "ready") return null;
    for (const stage of DEAL_STAGES) {
      const match = board.columns[stage].items.find(
        (item) => item.id === dealId,
      );
      if (match) return match;
    }
    return null;
  }

  function placeDeal(
    columns: Record<DealStage, Column>,
    deal: Deal,
    from: DealStage,
  ) {
    const next = { ...columns };
    next[from] = {
      items: next[from].items.filter((item) => item.id !== deal.id),
      total: Math.max(0, next[from].total - 1),
    };
    next[deal.stage] = {
      items: [deal, ...next[deal.stage].items],
      total: next[deal.stage].total + 1,
    };
    return next;
  }

  async function moveDeal(deal: Deal, stage: DealStage) {
    if (stage === deal.stage || moving || board.status !== "ready") return;
    if (!canChangeStage(deal, role)) {
      // The API would refuse with 403; say why instead of trying.
      toast.error({
        title: "This deal cannot be moved",
        description: WON_STAGE_LOCKED_MESSAGE,
      });
      return;
    }
    if (isClosedStage(stage)) {
      // Closing is consequential (and lost needs a reason): confirm in the dialog.
      setClosing({ deal, stage });
      return;
    }
    const before = board.columns;
    setMoving(deal.id);
    setBoard({
      status: "ready",
      columns: placeDeal(
        before,
        { ...deal, stage, forecast_category: forecastCategoryAfterMove(deal, stage) },
        deal.stage,
      ),
    });
    try {
      const saved = await changeDealStage(deal.id, {
        stage,
        expected_revision: deal.revision,
        probability: null,
        lost_reason: null,
        change_reason: null,
      });
      setBoard((current) =>
        current.status === "ready"
          ? {
              status: "ready",
              columns: {
                ...current.columns,
                [stage]: {
                  ...current.columns[stage],
                  items: current.columns[stage].items.map((item) =>
                    item.id === saved.id ? saved : item,
                  ),
                },
              },
            }
          : current,
      );
      toast.success({
        title: `Moved to ${DEAL_STAGE_LABELS[stage]}`,
        description: deal.name,
      });
      void getPipelineSummary(1)
        .then(setSummary)
        .catch(() => undefined);
    } catch (cause) {
      setBoard({ status: "ready", columns: before });
      toast.error({
        title: isRevisionConflict(cause)
          ? "This deal changed elsewhere"
          : "The deal could not be moved",
        description: isRevisionConflict(cause)
          ? "The board has been refreshed with the latest version. Try the move again if it is still needed."
          : cause instanceof ApiError && cause.status === 404
            ? "The deal no longer exists."
            : (forbiddenMessage(cause) ??
              "Nothing was changed. Please try again."),
      });
      if (
        isRevisionConflict(cause) ||
        (cause instanceof ApiError && cause.status === 404)
      )
        reload();
    } finally {
      setMoving(null);
    }
  }

  function onDrop(event: DragEvent<HTMLElement>, stage: DealStage) {
    event.preventDefault();
    setDropTarget(null);
    const deal = findDeal(event.dataTransfer.getData(DRAG_TYPE));
    if (deal) void moveDeal(deal, stage);
  }

  if (board.status === "loading") {
    return (
      <div className="flex gap-3 overflow-hidden" role="status">
        {DEAL_STAGES.map((stage) => (
          <Skeleton key={stage} className="h-80 w-72 shrink-0" />
        ))}
        <span className="sr-only">Loading pipeline</span>
      </div>
    );
  }

  if (board.status === "error") {
    return (
      <StatePanel
        kind="error"
        className="max-w-none"
        title="The pipeline could not be loaded"
        description="Check your connection and try again."
        action={
          <Button
            type="button"
            onClick={() => {
              setBoard({ status: "loading" });
              reload();
            }}
          >
            Retry
          </Button>
        }
      />
    );
  }

  const stageTotals = new Map(
    summary?.by_stage.map((row) => [row.stage, row]) ?? [],
  );

  return (
    <>
      <p className="text-muted-foreground text-xs" id="pipeline-board-help">
        Drag a card to another stage, or use its menu. Moving to Closed won or
        Closed lost asks for confirmation.
        {canManageDeals(role)
          ? null
          : " Only owners and admins can move won deals."}
      </p>
      <div
        className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-3 sm:mx-0 sm:px-0"
        aria-describedby="pipeline-board-help"
      >
        {DEAL_STAGES.map((stage) => {
          const column = board.columns[stage];
          const totals = stageTotals.get(stage);
          return (
            <section
              key={stage}
              aria-label={`${DEAL_STAGE_LABELS[stage]}, ${column.total} ${column.total === 1 ? "deal" : "deals"}`}
              onDragOver={(event) => {
                if (!event.dataTransfer.types.includes(DRAG_TYPE)) return;
                event.preventDefault();
                setDropTarget(stage);
              }}
              onDragLeave={() =>
                setDropTarget((current) => (current === stage ? null : current))
              }
              onDrop={(event) => onDrop(event, stage)}
              className={cn(
                "bg-surface-subtle border-border flex w-72 shrink-0 snap-start flex-col rounded-xl border transition-colors",
                dropTarget === stage && "border-brand bg-brand-subtle",
              )}
            >
              <header className="border-border flex items-center justify-between gap-2 border-b px-3 py-2.5">
                <div className="flex min-w-0 items-center gap-2">
                  <StatusBadge
                    status={
                      stage === "CLOSED_WON"
                        ? "success"
                        : stage === "CLOSED_LOST"
                          ? "failed"
                          : "draft"
                    }
                    label={DEAL_STAGE_LABELS[stage]}
                  />
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {column.total}
                  </span>
                </div>
                {totals && summary ? (
                  <span
                    className="text-xs font-medium tabular-nums"
                    title={formatMoney(totals.total_amount, summary.currency)}
                  >
                    {formatMoneyCompact(totals.total_amount, summary.currency)}
                  </span>
                ) : null}
              </header>
              <ul
                className="grid content-start gap-2 p-2"
                aria-label={`${DEAL_STAGE_LABELS[stage]} deals`}
              >
                {column.items.length === 0 ? (
                  <li className="text-muted-foreground border-border rounded-lg border border-dashed px-3 py-6 text-center text-xs">
                    No deals in this stage
                  </li>
                ) : (
                  column.items.map((deal) => (
                    <DealCard
                      key={deal.id}
                      deal={deal}
                      locked={!canChangeStage(deal, role)}
                      moving={moving === deal.id}
                      onOpen={setDrawerDeal}
                      onMove={(target, next) => void moveDeal(target, next)}
                    />
                  ))
                )}
              </ul>
              {column.total > column.items.length ? (
                <Link
                  href={`${DEALS_PATH}?stage=${stage}`}
                  className="text-brand-text px-3 pb-3 text-xs font-medium underline-offset-4 hover:underline"
                >
                  View all {column.total} in the list
                </Link>
              ) : null}
            </section>
          );
        })}
      </div>

      <DealDrawer
        key={drawerDeal?.id ?? "none"}
        deal={drawerDeal}
        onOpenChange={(open) => {
          if (!open) setDrawerDeal(null);
        }}
      />

      {closing ? (
        <DealStageDialog
          key={`${closing.deal.id}-${closing.stage}`}
          open
          onOpenChange={(open) => {
            if (!open) setClosing(null);
          }}
          deal={closing.deal}
          initialStage={closing.stage}
          role={role}
          onSaved={(saved) => {
            toast.success({
              title: `Moved to ${DEAL_STAGE_LABELS[saved.stage]}`,
              description: saved.name,
            });
            setClosing(null);
            reload();
          }}
          onReload={async () => {
            try {
              const latest = await getDeal(closing.deal.id);
              reload();
              return latest;
            } catch {
              return null;
            }
          }}
        />
      ) : null}
    </>
  );
}
