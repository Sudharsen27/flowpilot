"use client";

import { useEffect, useId, useRef, useState } from "react";

import { StatePanel } from "@/components/data-display/state-panel";
import { Button } from "@/components/ui/button";
import { getCrmCompany, type CrmCompanySummary } from "@/lib/api/crm-companies";
import { listCrmContacts, type CrmContact } from "@/lib/api/crm-contacts";

const PAGE_SIZE = 100;
const MAX_COMPANY_LOOKUPS = 5;

type CompanyLookup =
  | { status: "loading" }
  | { status: "ready"; company: CrmCompanySummary }
  | { status: "error" };

type ProjectionState =
  | { status: "loading" }
  | { status: "error"; offset: number }
  | {
      status: "ready";
      offset: number;
      items: CrmContact[];
      total: number;
      companies: Record<string, CompanyLookup>;
    };

export function DealCrmProjection({ leadId }: { leadId: string | null }) {
  const titleId = useId();
  return (
    <section
      className="border-border grid gap-4 border-t pt-5"
      aria-labelledby={titleId}
    >
      <h2 id={titleId} className="text-sm font-medium">
        CRM Contacts and Companies
      </h2>
      {leadId ? (
        <DealCrmProjectionForLead key={leadId} leadId={leadId} />
      ) : (
        <p className="text-muted-foreground text-sm">
          No Lead is associated with this Deal.
        </p>
      )}
    </section>
  );
}

function DealCrmProjectionForLead({ leadId }: { leadId: string }) {
  const [offset, setOffset] = useState(0);
  const [retryKey, setRetryKey] = useState(0);
  const [state, setState] = useState<ProjectionState>({
    status: "loading",
  });
  const companyCache = useRef(new Map<string, CompanyLookup>());

  useEffect(() => {
    const controller = new AbortController();

    async function loadProjection() {
      const page = await listCrmContacts(
        {
          leadId,
          includeArchived: true,
          limit: PAGE_SIZE,
          offset,
        },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) {
        return;
      }
      if (page.items.length === 0 && offset > 0) {
        setOffset(Math.max(0, offset - PAGE_SIZE));
        return;
      }

      const companyIds = [
        ...new Set(
          page.items
            .map((contact) => contact.company_id)
            .filter((companyId): companyId is string => companyId !== null),
        ),
      ];
      const companies = Object.fromEntries(
        companyIds.map((companyId) => [
          companyId,
          companyCache.current.get(companyId) ?? { status: "loading" },
        ]),
      ) as Record<string, CompanyLookup>;
      const missingCompanyIds = companyIds.filter(
        (companyId) => !companyCache.current.has(companyId),
      );

      setState({
        status: "ready",
        offset,
        items: page.items,
        total: page.total,
        companies,
      });

      let nextCompanyIndex = 0;
      const workers = Array.from(
        { length: Math.min(MAX_COMPANY_LOOKUPS, missingCompanyIds.length) },
        async () => {
          while (!controller.signal.aborted) {
            const companyId = missingCompanyIds[nextCompanyIndex];
            nextCompanyIndex += 1;
            if (!companyId) {
              return;
            }
            try {
              const company = await getCrmCompany(companyId, {
                signal: controller.signal,
              });
              if (!controller.signal.aborted) {
                companyCache.current.set(companyId, {
                  status: "ready",
                  company,
                });
              }
            } catch {
              if (!controller.signal.aborted) {
                companyCache.current.set(companyId, { status: "error" });
              }
            }
          }
        },
      );
      await Promise.all(workers);

      if (!controller.signal.aborted) {
        setState((current) => {
          if (current.status !== "ready" || current.offset !== offset) {
            return current;
          }
          return {
            ...current,
            companies: Object.fromEntries(
              companyIds.map((companyId) => [
                companyId,
                companyCache.current.get(companyId) ?? { status: "error" },
              ]),
            ),
          };
        });
      }
    }

    void loadProjection().catch(() => {
      if (!controller.signal.aborted) {
        setState({ status: "error", offset });
      }
    });

    return () => controller.abort();
  }, [leadId, offset, retryKey]);

  function retry() {
    for (const [companyId, lookup] of companyCache.current) {
      if (lookup.status === "error") {
        companyCache.current.delete(companyId);
      }
    }
    setState({ status: "loading" });
    setRetryKey((key) => key + 1);
  }

  const currentState =
    state.status !== "loading" && state.offset === offset ? state : null;
  const isLoading = currentState === null;

  return (
    <>
      {currentState?.status === "error" ? (
        <StatePanel
          kind="error"
          className="max-w-none"
          headingLevel={3}
          title="CRM Contacts could not be loaded"
          description="Check your connection and try again."
          action={
            <Button type="button" size="sm" onClick={retry}>
              Retry CRM Contacts
            </Button>
          }
        />
      ) : isLoading ? (
        <p className="text-muted-foreground text-sm" role="status">
          Loading CRM Contacts…
        </p>
      ) : currentState?.status === "ready" ? (
        <>
          {currentState.items.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No CRM Contacts are associated with this Lead.
            </p>
          ) : (
            <ul className="grid gap-2">
              {currentState.items.map((contact) => {
                const company = contact.company_id
                  ? currentState.companies[contact.company_id]
                  : undefined;
                return (
                  <li
                    key={contact.id}
                    className="border-border grid gap-2 rounded-md border p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium">
                        {contact.display_name}
                      </p>
                      {contact.archived_at ? (
                        <span className="text-warning-text mt-1 inline-block text-xs font-medium">
                          Archived Contact
                        </span>
                      ) : null}
                    </div>
                    <div className="text-muted-foreground text-sm">
                      {!contact.company_id ? (
                        <p>No CRM Company associated</p>
                      ) : company?.status === "ready" ? (
                        <p>
                          CRM Company: {company.company.name}
                          {company.company.archived_at ? (
                            <span className="text-warning-text ml-2 text-xs font-medium">
                              Archived Company
                            </span>
                          ) : null}
                        </p>
                      ) : company?.status === "error" ? (
                        <p>CRM Company details unavailable</p>
                      ) : (
                        <p role="status">Loading CRM Company…</p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          {Object.values(currentState.companies).some(
            (company) => company.status === "error",
          ) ? (
            <div className="grid gap-2">
              <p className="text-danger-text text-sm" role="alert">
                Some CRM Company details could not be loaded. Contacts are still
                shown.
              </p>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="w-fit"
                onClick={retry}
              >
                Retry Company lookups
              </Button>
            </div>
          ) : null}
          {currentState.total > PAGE_SIZE ? (
            <div className="flex items-center justify-between gap-3">
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={currentState.offset === 0}
                onClick={() =>
                  setOffset(Math.max(0, currentState.offset - PAGE_SIZE))
                }
              >
                Previous Contacts
              </Button>
              <span className="text-muted-foreground text-xs tabular-nums">
                {currentState.offset + 1}–
                {Math.min(currentState.offset + PAGE_SIZE, currentState.total)}{" "}
                of {currentState.total}
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={currentState.offset + PAGE_SIZE >= currentState.total}
                onClick={() => setOffset(currentState.offset + PAGE_SIZE)}
              >
                Next Contacts
              </Button>
            </div>
          ) : null}
        </>
      ) : null}
    </>
  );
}
