"use client";

import { useEffect, useState } from "react";

import { AnalyticsOverview } from "@/components/analytics/analytics-overview";
import {
  AnalyticsPanel,
  AnalyticsPanelGrid,
  type AnalyticsPanelRow,
} from "@/components/analytics/analytics-panel";
import {
  AnalyticsToolbar,
  leadSourceLabels,
} from "@/components/analytics/analytics-toolbar";
import { AnalyticsTrend } from "@/components/analytics/analytics-trend";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { getAnalyticsSummary } from "@/lib/api/analytics";
import type {
  AnalyticsRangeDays,
  AnalyticsSummary,
  LeadSource,
} from "@/types/api";

function count(value: number) {
  return value.toLocaleString();
}

function rate(part: number, whole: number) {
  return whole > 0 ? `${Math.round((part / whole) * 100)}%` : "—";
}

function leadRows(summary: AnalyticsSummary): AnalyticsPanelRow[] {
  const outcomes = summary.qualification_outcomes;
  const assessed =
    outcomes.qualified + outcomes.unqualified + outcomes.needs_more_information;
  return [
    {
      label: "Qualified",
      value: count(outcomes.qualified),
      hint: `${rate(outcomes.qualified, assessed)} of AI assessments`,
    },
    { label: "Unqualified", value: count(outcomes.unqualified) },
    {
      label: "Needs more information",
      value: count(outcomes.needs_more_information),
    },
  ];
}

function sourceRows(summary: AnalyticsSummary): AnalyticsPanelRow[] {
  return summary.leads_by_source.map((item) => ({
    label: leadSourceLabels[item.source],
    value: count(item.count),
    hint: `${rate(item.count, summary.totals.leads_created)} of new leads`,
  }));
}

function replyRows(summary: AnalyticsSummary): AnalyticsPanelRow[] {
  const totals = summary.totals;
  return [
    { label: "AI reply drafts", value: count(totals.ai_drafts) },
    {
      label: "Drafts approved by a person",
      value: count(totals.drafts_approved),
      hint: `${rate(totals.drafts_approved, totals.ai_drafts)} of drafts`,
    },
    { label: "Emails sent", value: count(totals.emails_sent) },
  ];
}

function followUpRows(summary: AnalyticsSummary): AnalyticsPanelRow[] {
  const totals = summary.totals;
  return [
    {
      label: "Follow-ups completed",
      value: count(totals.follow_ups_completed),
    },
    {
      label: "Customer replies received",
      value: count(totals.customer_replies),
    },
    { label: "Human handoffs", value: count(totals.human_handoffs) },
  ];
}

export default function AnalyticsPage() {
  const [rangeDays, setRangeDays] = useState<AnalyticsRangeDays>(30);
  const [source, setSource] = useState<LeadSource | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getAnalyticsSummary({ rangeDays, source })
      .then((data) => {
        if (cancelled) return;
        setSummary(data);
        setError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setSummary(null);
        setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [rangeDays, source, retryKey]);

  function changeFilters(next: {
    rangeDays?: AnalyticsRangeDays;
    source?: LeadSource | null;
  }) {
    setLoading(true);
    if (next.rangeDays !== undefined) setRangeDays(next.rangeDays);
    if (next.source !== undefined) setSource(next.source);
  }

  const busy = loading && !error;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Analytics"
        description="How leads, AI work, and replies are moving in your workspace. Numbers come from your own records and update when you change the filters."
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Reporting period"
          description="Choose the period and lead source to report on."
        />
        <AnalyticsToolbar
          rangeDays={rangeDays}
          source={source}
          onRangeDaysChange={(value) => changeFilters({ rangeDays: value })}
          onSourceChange={(value) => changeFilters({ source: value })}
        />
      </section>

      {error ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          title="Analytics could not be loaded"
          description="Check your connection and try again."
          action={
            <Button
              type="button"
              onClick={() => {
                setLoading(true);
                setError(false);
                setRetryKey((value) => value + 1);
              }}
            >
              Retry
            </Button>
          }
        />
      ) : (
        <>
          <section className="grid gap-5">
            <SectionHeader
              title="Overview"
              description="Totals for the selected period."
            />
            <AnalyticsOverview summary={summary} loading={busy} />
          </section>

          <section className="grid gap-5">
            <SectionHeader
              title="Performance"
              description="Where leads come from, how the AI assessed them, and what happened to replies."
            />
            <AnalyticsTrend daily={summary?.daily ?? []} loading={busy} />
            <AnalyticsPanelGrid>
              <AnalyticsPanel
                headingId="lead-performance-title"
                title="AI lead assessment"
                description="Results of every completed AI analysis in this period."
                rows={summary ? leadRows(summary) : []}
                loading={busy}
              />
              <AnalyticsPanel
                headingId="lead-sources-title"
                title="Lead sources"
                description="Where new leads came from."
                rows={summary ? sourceRows(summary) : []}
                loading={busy}
                emptyMessage="No new leads in this period."
              />
              <AnalyticsPanel
                headingId="reply-performance-title"
                title="Replies and approvals"
                description="AI writes drafts. A person approves each one before it is sent."
                rows={summary ? replyRows(summary) : []}
                loading={busy}
              />
              <AnalyticsPanel
                headingId="outcomes-title"
                title="Follow-up and handoffs"
                description="Work that needed or came back from a person."
                rows={summary ? followUpRows(summary) : []}
                loading={busy}
              />
            </AnalyticsPanelGrid>
          </section>
        </>
      )}
    </div>
  );
}
