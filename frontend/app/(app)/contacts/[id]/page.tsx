"use client";

import Link from "next/link";
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
import { getCrmCompany, type CrmCompanySummary } from "@/lib/api/crm-companies";
import { getCrmContact, type CrmContact } from "@/lib/api/crm-contacts";
import { formatAbsoluteTimestamp } from "@/lib/datetime";

type LoadError = {
  contactId: string;
  kind: "not-found" | "error";
};

type CompanyLookup =
  | { companyId: string; status: "loading" }
  | { companyId: string; status: "ready"; company: CrmCompanySummary }
  | { companyId: string; status: "error" };

function contactStatusLabel(status: CrmContact["status"]) {
  return status === "ACTIVE" ? "Active" : "Inactive";
}

export default function ContactDetailPage() {
  const params = useParams<{ id: string }>();
  const contactId = params.id;
  const [contact, setContact] = useState<CrmContact | null>(null);
  const [companyLookup, setCompanyLookup] = useState<CompanyLookup | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<LoadError | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    void getCrmContact(contactId, { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return;
        setContact(data);
        if (!data.company_id) {
          setCompanyLookup(null);
          return;
        }

        const companyId = data.company_id;
        setCompanyLookup({ companyId, status: "loading" });
        void getCrmCompany(data.company_id, { signal: controller.signal })
          .then((companyData) => {
            if (!controller.signal.aborted) {
              setCompanyLookup({
                companyId,
                status: "ready",
                company: companyData,
              });
            }
          })
          .catch(() => {
            if (!controller.signal.aborted) {
              setCompanyLookup({ companyId, status: "error" });
            }
          });
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return;
        setContact(null);
        setLoadError({
          contactId,
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
  }, [contactId, retryKey]);

  function retry() {
    setLoading(true);
    setLoadError(null);
    setRetryKey((value) => value + 1);
  }

  const currentContact = contact?.id === contactId ? contact : null;
  const currentError =
    loadError?.contactId === contactId ? loadError.kind : null;
  const currentCompanyLookup =
    currentContact && companyLookup?.companyId === currentContact.company_id
      ? companyLookup
      : null;

  if (loading || (!currentContact && !currentError)) {
    return (
      <div className="gap-section flex flex-col" aria-busy="true">
        <PageHeader title="Loading Contact" />
        <div
          className="border-border grid gap-4 rounded-lg border p-5"
          role="status"
        >
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-24 w-full" />
          <span className="sr-only">Loading Contact</span>
        </div>
      </div>
    );
  }

  if (!currentContact) {
    const notFound = currentError === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          title={notFound ? "Contact not found" : "Contact unavailable"}
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={
            notFound
              ? "This Contact could not be found."
              : "Unable to load Contact"
          }
          description={
            notFound
              ? "The Contact may have been removed or may not be available in your organization."
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

  const statusTone = currentContact.status === "ACTIVE" ? "active" : "paused";
  const linkedCompany =
    currentCompanyLookup?.status === "ready"
      ? currentCompanyLookup.company
      : null;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title={currentContact.display_name}
        titleBadge={
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              status={statusTone}
              label={contactStatusLabel(currentContact.status)}
            />
            {currentContact.archived_at ? (
              <StatusBadge status="paused" label="Archived" />
            ) : null}
          </div>
        }
        description="CRM Contact record."
      />

      <section
        className="border-border grid gap-5 rounded-lg border p-4 sm:p-5"
        aria-labelledby="contact-information-title"
      >
        <div>
          <h2
            id="contact-information-title"
            className="text-section-title font-semibold tracking-tight"
          >
            Contact information
          </h2>
        </div>
        <dl className="grid gap-4 sm:grid-cols-2">
          <DetailRow label="Name" value={currentContact.display_name} />
          <DetailRow
            label="First name"
            value={currentContact.first_name ?? "Not provided"}
          />
          <DetailRow
            label="Last name"
            value={currentContact.last_name ?? "Not provided"}
          />
          <DetailRow
            label="Job title"
            value={currentContact.job_title ?? "Not provided"}
          />
          <DetailRow
            label="Email"
            value={
              currentContact.email ? (
                <a
                  className="underline underline-offset-4"
                  href={`mailto:${currentContact.email}`}
                >
                  {currentContact.email}
                </a>
              ) : (
                "Not provided"
              )
            }
          />
          <DetailRow
            label="Phone"
            value={
              currentContact.phone ? (
                <a
                  className="underline underline-offset-4"
                  href={`tel:${currentContact.phone}`}
                >
                  {currentContact.phone}
                </a>
              ) : (
                "Not provided"
              )
            }
          />
          <DetailRow
            label="Mobile"
            value={
              currentContact.mobile ? (
                <a
                  className="underline underline-offset-4"
                  href={`tel:${currentContact.mobile}`}
                >
                  {currentContact.mobile}
                </a>
              ) : (
                "Not provided"
              )
            }
          />
          <DetailRow
            label="Company"
            value={
              currentContact.company_id ? (
                <div className="grid justify-items-start gap-1">
                  <Link
                    className="underline underline-offset-4"
                    href={`/companies/${encodeURIComponent(currentContact.company_id)}`}
                  >
                    {linkedCompany?.name ?? "Open associated Company"}
                  </Link>
                  {currentCompanyLookup?.status === "loading" ? (
                    <span className="text-muted-foreground text-xs">
                      Loading Company details…
                    </span>
                  ) : null}
                  {currentCompanyLookup?.status === "error" ? (
                    <span
                      className="text-muted-foreground text-xs"
                      role="status"
                    >
                      Company details are unavailable.
                    </span>
                  ) : null}
                </div>
              ) : (
                "No Company associated"
              )
            }
          />
          <DetailRow
            label="Owner"
            value={currentContact.owner_user_id ?? "Unassigned"}
          />
          <DetailRow
            label="Source"
            value={currentContact.source.replaceAll("_", " ")}
          />
          <DetailRow
            label="Status"
            value={contactStatusLabel(currentContact.status)}
          />
          <DetailRow
            label="Archived"
            value={
              currentContact.archived_at
                ? (formatAbsoluteTimestamp(currentContact.archived_at) ??
                  "Archived")
                : "No"
            }
          />
          <DetailRow
            label="LinkedIn"
            value={currentContact.linkedin_url ?? "Not provided"}
            className="sm:col-span-2"
          />
          <DetailRow
            label="Description"
            value={currentContact.description ?? "No description"}
            className="sm:col-span-2"
          />
          <DetailRow
            label="Created"
            value={
              formatAbsoluteTimestamp(currentContact.created_at) ??
              "Date unavailable"
            }
          />
          <DetailRow
            label="Last updated"
            value={
              formatAbsoluteTimestamp(currentContact.updated_at) ??
              "Date unavailable"
            }
          />
        </dl>
      </section>

      <EntityActivityTimeline entityType="CONTACT" entityId={contactId} />
    </div>
  );
}
