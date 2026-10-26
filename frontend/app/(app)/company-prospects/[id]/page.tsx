"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  CompanyProspectStatusBadge,
  EvidenceQualityBadge,
} from "@/components/company-prospects/company-prospect-badges";
import { StatePanel } from "@/components/data-display/state-panel";
import { PageHeader } from "@/components/page-header";
import { Button, buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import { getCompanyProspect } from "@/lib/api/company-prospects";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import type { CompanyProspect } from "@/types/api";

export default function CompanyProspectDetailPage() {
  const params = useParams<{ id: string }>();
  const prospectId = params.id;
  const [prospect, setProspect] = useState<CompanyProspect | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorKind, setErrorKind] = useState<"not-found" | "error" | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void getCompanyProspect(prospectId)
      .then((data) => {
        if (!cancelled) {
          setProspect(data);
          setErrorKind(null);
        }
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setProspect(null);
          setErrorKind(
            cause instanceof ApiError && cause.status === 404 ? "not-found" : "error",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [prospectId, retryKey]);

  function retry() {
    setLoading(true);
    setErrorKind(null);
    setRetryKey((value) => value + 1);
  }

  if (loading) {
    return (
      <div className="gap-section flex flex-col" aria-busy="true">
        <PageHeader
          breadcrumbs={[{ label: "Company Prospects", href: "/company-prospects" }, { label: "Loading" }]}
          title="Loading company prospect"
        />
        <div className="border-border grid gap-4 rounded-lg border p-5">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
    );
  }

  if (!prospect) {
    const notFound = errorKind === "not-found";
    return (
      <div className="gap-section flex flex-col">
        <PageHeader
          breadcrumbs={[
            { label: "Company Prospects", href: "/company-prospects" },
            { label: notFound ? "Not found" : "Unavailable" },
          ]}
          title={notFound ? "Company prospect not found" : "Company prospect unavailable"}
        />
        <StatePanel
          kind="error"
          className="max-w-none"
          title={notFound ? "This company prospect could not be found." : "Unable to load company prospect"}
          description={
            notFound
              ? "Return to Company Prospects to select an available record."
              : "Check your connection and try again."
          }
          action={
            <div className="flex flex-wrap gap-2">
              {!notFound ? <Button type="button" onClick={retry}>Retry</Button> : null}
              <Link href="/company-prospects" className={buttonVariants({ variant: "outline" })}>
                Back to Company Prospects
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        breadcrumbs={[{ label: "Company Prospects", href: "/company-prospects" }, { label: prospect.name }]}
        title={prospect.name}
        titleBadge={<CompanyProspectStatusBadge status={prospect.status} />}
        description="Saved company record. No enrichment, import, or automation is available here."
        secondaryActions={
          <Link href="/company-prospects" className={buttonVariants({ variant: "outline" })}>
            Back to Company Prospects
          </Link>
        }
      />

      <section className="border-border grid gap-5 rounded-lg border p-4 sm:p-5" aria-labelledby="company-information-title">
        <div>
          <h2 id="company-information-title" className="text-section-title font-semibold tracking-tight">
            Company information
          </h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Values and confidence labels saved on this record.
          </p>
        </div>
        <dl className="grid gap-5 sm:grid-cols-2">
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Company name</dt>
            <dd className="font-medium">{prospect.name}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Name evidence</dt>
            <dd><EvidenceQualityBadge quality={prospect.name_evidence_quality} /></dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Website domain</dt>
            <dd className="break-all">{prospect.website_domain ?? "No domain recorded"}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Domain evidence</dt>
            <dd><EvidenceQualityBadge quality={prospect.website_domain_evidence_quality} /></dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Created</dt>
            <dd>{formatAbsoluteTimestamp(prospect.created_at) ?? "Date unavailable"}</dd>
          </div>
          <div className="grid gap-1">
            <dt className="text-muted-foreground text-sm">Last updated</dt>
            <dd>{formatAbsoluteTimestamp(prospect.updated_at) ?? "Date unavailable"}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
