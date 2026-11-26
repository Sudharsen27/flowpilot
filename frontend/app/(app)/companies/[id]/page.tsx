"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { DetailRow } from "@/components/data-display/detail-row";
import { StatePanel } from "@/components/data-display/state-panel";
import { EntityActivityTimeline } from "@/components/activity/entity-activity-timeline";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import { getCrmCompany, type CrmCompanyDetail } from "@/lib/api/crm-companies";
import { formatAbsoluteTimestamp } from "@/lib/datetime";

type LoadError = {
  companyId: string;
  kind: "not-found" | "error";
};

const lifecycleLabels = {
  PROSPECT: "Prospect",
  CUSTOMER: "Customer",
  FORMER_CUSTOMER: "Former customer",
  PARTNER: "Partner",
} as const;

const lifecycleTones = {
  PROSPECT: "pending",
  CUSTOMER: "success",
  FORMER_CUSTOMER: "paused",
  PARTNER: "active",
} as const;

export default function CompanyDetailPage() {
  const params = useParams<{ id: string }>();
  const companyId = params.id;
  const [company, setCompany] = useState<CrmCompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<LoadError | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    void getCrmCompany(companyId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setCompany(data);
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setCompany(null);
        setLoadError({
          companyId,
          kind:
            cause instanceof ApiError && cause.status === 404
              ? "not-found"
              : "error",
        });
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [companyId, retryKey]);

  function retry() {
    setLoading(true);
    setLoadError(null);
    setRetryKey((value) => value + 1);
  }

  const currentCompany = company?.id === companyId ? company : null;
  const currentError =
    loadError?.companyId === companyId ? loadError.kind : null;

  if (loading || (!currentCompany && !currentError)) {
    return (
      <div className="gap-section flex flex-col" aria-busy="true">
        <PageHeader title="Loading Company" />
        <div
          className="border-border grid gap-4 rounded-lg border p-5"
          role="status"
        >
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-24 w-full" />
          <span className="sr-only">Loading Company</span>
        </div>
      </div>
    );
  }

  if (!currentCompany) {
    const notFound = currentError === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          title={notFound ? "Company not found" : "Company unavailable"}
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={
            notFound
              ? "This Company could not be found."
              : "Unable to load Company"
          }
          description={
            notFound
              ? "The Company may have been removed or may not be available in your organization."
              : "Check your connection and try again."
          }
          action={
            !notFound ? (
              <Button type="button" onClick={retry}>
                Retry
              </Button>
            ) : null
          }
        />
      </div>
    );
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title={currentCompany.name}
        titleBadge={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              status={lifecycleTones[currentCompany.lifecycle_status]}
              label={lifecycleLabels[currentCompany.lifecycle_status]}
            />
            {currentCompany.archived_at ? (
              <StatusBadge status="paused" label="Archived" />
            ) : null}
          </div>
        }
        description="CRM Company record."
      />

      <section
        className="border-border grid gap-5 rounded-lg border p-4 sm:p-5"
        aria-labelledby="company-information-title"
      >
        <div>
          <h2
            id="company-information-title"
            className="text-section-title font-semibold tracking-tight"
          >
            Company information
          </h2>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <DetailRow label="Name" value={currentCompany.name} />
          <DetailRow
            label="Website domain"
            value={currentCompany.website_domain ?? "Not provided"}
          />
          <DetailRow
            label="Owner"
            value={currentCompany.owner_user_id ?? "Unassigned"}
          />
          <DetailRow
            label="Status"
            value={lifecycleLabels[currentCompany.lifecycle_status]}
          />
          <DetailRow
            label="Industry"
            value={currentCompany.industry ?? "Not provided"}
          />
          <DetailRow
            label="Employee count"
            value={
              currentCompany.employee_count?.toLocaleString() ?? "Not provided"
            }
          />
          <DetailRow
            label="Phone"
            value={currentCompany.phone ?? "Not provided"}
          />
          <DetailRow
            label="Email"
            value={currentCompany.email ?? "Not provided"}
          />
          <DetailRow
            label="Address"
            value={
              [
                currentCompany.address_line1,
                currentCompany.address_line2,
                currentCompany.city,
                currentCompany.region,
                currentCompany.postal_code,
                currentCompany.country,
              ]
                .filter(Boolean)
                .join(", ") || "Not provided"
            }
            className="sm:col-span-2"
          />
          <DetailRow
            label="Source"
            value={currentCompany.source.replaceAll("_", " ")}
          />
          <DetailRow
            label="Archived"
            value={
              currentCompany.archived_at
                ? (formatAbsoluteTimestamp(currentCompany.archived_at) ??
                  "Archived")
                : "No"
            }
          />
          <DetailRow
            label="Description"
            value={currentCompany.description ?? "No description"}
            className="sm:col-span-2"
          />
          <DetailRow
            label="Created"
            value={
              formatAbsoluteTimestamp(currentCompany.created_at) ??
              "Date unavailable"
            }
          />
          <DetailRow
            label="Last updated"
            value={
              formatAbsoluteTimestamp(currentCompany.updated_at) ??
              "Date unavailable"
            }
          />
        </dl>
      </section>

      <EntityActivityTimeline entityType="COMPANY" entityId={companyId} />
    </div>
  );
}
