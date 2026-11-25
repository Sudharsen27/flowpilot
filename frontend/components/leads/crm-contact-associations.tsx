"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/forms/input";
import { ApiError } from "@/lib/api/client";
import { getCrmCompany } from "@/lib/api/crm-companies";
import {
  listCrmContacts,
  updateCrmContactLeadLink,
  type CrmContact,
} from "@/lib/api/crm-contacts";

const PAGE_SIZE = 20;
const LINKED_SEARCH_PAGE_SIZE = 100;

type ContactPage = {
  items: CrmContact[];
  total: number;
};

type LinkedSearchCache = {
  leadId: string;
  query: string;
  refreshVersion: number;
  items: CrmContact[];
  total: number;
};

function apiDetail(error: ApiError): string | null {
  if (
    typeof error.body === "object" &&
    error.body !== null &&
    "detail" in error.body &&
    typeof error.body.detail === "string"
  ) {
    return error.body.detail;
  }
  return null;
}

function mutationErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "The Contact association could not be changed. Check your connection and try again.";
  }
  if (error.status === 403) {
    return "You do not have permission to change this Contact's Lead associations.";
  }
  if (error.status === 404) {
    return "The Contact or Lead is no longer available. Refresh and try again.";
  }
  if (error.status === 409) {
    const detail = apiDetail(error);
    if (detail?.toLowerCase().includes("archived")) {
      return "Archived Contacts cannot be linked or unlinked. Restore the Contact first.";
    }
    return "This Contact changed after it was loaded. The latest associations are being refreshed; review them and try again.";
  }
  return (
    apiDetail(error) ??
    "The Contact association could not be changed. Try again."
  );
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to view these Contacts.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "This Lead or its Contacts could not be found.";
  }
  return "Contacts could not be loaded. Check your connection and retry.";
}

export function CrmContactAssociations({ leadId }: { leadId: string }) {
  const [linkedPage, setLinkedPage] = useState<ContactPage>({
    items: [],
    total: 0,
  });
  const [linkedOffset, setLinkedOffset] = useState(0);
  const [linkedLoading, setLinkedLoading] = useState(true);
  const [linkedError, setLinkedError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [searchOffset, setSearchOffset] = useState(0);
  const [candidates, setCandidates] = useState<ContactPage>({
    items: [],
    total: 0,
  });
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [companyNames, setCompanyNames] = useState<Record<string, string>>({});
  const [companyErrors, setCompanyErrors] = useState<Record<string, boolean>>(
    {},
  );
  const [linkedSearchIds, setLinkedSearchIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [pendingContactId, setPendingContactId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const mutationInProgress = useRef(false);
  const companyNameCache = useRef(new Map<string, string>());
  const linkedSearchCache = useRef<LinkedSearchCache | null>(null);

  const linkedIds = useMemo(
    () => new Set(linkedPage.items.map((contact) => contact.id)),
    [linkedPage.items],
  );
  const availableCandidates = candidates.items.filter(
    (contact) => !linkedIds.has(contact.id) && !linkedSearchIds.has(contact.id),
  );
  const normalizedSearch = search.trim();

  useEffect(() => {
    const controller = new AbortController();
    let changingPage = false;
    void listCrmContacts(
      {
        leadId,
        includeArchived: true,
        limit: PAGE_SIZE,
        offset: linkedOffset,
      },
      { signal: controller.signal },
    )
      .then(async (page) => {
        if (controller.signal.aborted) {
          return;
        }
        if (page.items.length === 0 && linkedOffset > 0) {
          changingPage = true;
          setLinkedLoading(true);
          setLinkedOffset(Math.max(0, linkedOffset - PAGE_SIZE));
          return;
        }
        setLinkedPage({ items: page.items, total: page.total });
        setCompanyNames(
          Object.fromEntries(
            page.items.flatMap((contact) => {
              const companyId = contact.company_id;
              const name = companyId
                ? companyNameCache.current.get(companyId)
                : undefined;
              return companyId && name ? [[companyId, name]] : [];
            }),
          ),
        );
        setCompanyErrors({});
        const companyIds = [
          ...new Set(
            page.items
              .map((contact) => contact.company_id)
              .filter((id): id is string => Boolean(id)),
          ),
        ];
        const companyResults = await Promise.all(
          companyIds
            .filter((companyId) => !companyNameCache.current.has(companyId))
            .map(async (companyId) => {
              try {
                const company = await getCrmCompany(companyId, {
                  signal: controller.signal,
                });
                return { companyId, name: company.name };
              } catch {
                return { companyId, name: null };
              }
            }),
        );
        if (controller.signal.aborted) {
          return;
        }
        for (const result of companyResults) {
          if (result.name !== null) {
            companyNameCache.current.set(result.companyId, result.name);
          }
        }
        setCompanyNames(
          Object.fromEntries(
            companyResults
              .filter(
                (result): result is { companyId: string; name: string } =>
                  result.name !== null,
              )
              .map(({ companyId, name }) => [companyId, name]),
          ),
        );
        setCompanyErrors(
          Object.fromEntries(
            companyResults
              .filter((result) => result.name === null)
              .map(({ companyId }) => [companyId, true]),
          ),
        );
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLinkedError(requestErrorMessage(error));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted && !changingPage) {
          setLinkedLoading(false);
        }
      });
    return () => controller.abort();
  }, [leadId, linkedOffset, refreshVersion]);

  useEffect(() => {
    const controller = new AbortController();
    if (!normalizedSearch) {
      return () => controller.abort();
    }

    const timeout = window.setTimeout(() => {
      async function loadSearchResults() {
        const cached = linkedSearchCache.current;
        const cache =
          cached?.leadId === leadId &&
          cached.query === normalizedSearch &&
          cached.refreshVersion === refreshVersion
            ? cached
            : {
                leadId,
                query: normalizedSearch,
                refreshVersion,
                items: [],
                total: 0,
              };
        linkedSearchCache.current = cache;

        async function loadLinkedContactsThrough(requiredCount: number) {
          while (
            cache.items.length < requiredCount &&
            (cache.items.length === 0 || cache.items.length < cache.total)
          ) {
            const page = await listCrmContacts(
              {
                q: normalizedSearch,
                leadId,
                limit: LINKED_SEARCH_PAGE_SIZE,
                offset: cache.items.length,
              },
              { signal: controller.signal },
            );
            if (controller.signal.aborted) {
              return;
            }
            cache.total = page.total;
            cache.items.push(...page.items);
            if (page.items.length === 0) {
              return;
            }
          }
        }

        const page = await listCrmContacts(
          {
            q: normalizedSearch,
            limit: PAGE_SIZE,
            offset: searchOffset,
          },
          { signal: controller.signal },
        );
        if (!controller.signal.aborted && page.items.length > 0) {
          await loadLinkedContactsThrough(searchOffset + page.items.length);
        }
        if (!controller.signal.aborted) {
          setCandidates({ items: page.items, total: page.total });
          setLinkedSearchIds(new Set(cache.items.map((contact) => contact.id)));
        }
      }

      void loadSearchResults()
        .catch((error: unknown) => {
          if (!controller.signal.aborted) {
            setSearchError(requestErrorMessage(error));
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setSearchLoading(false);
          }
        });
    }, 250);
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [leadId, normalizedSearch, searchOffset, refreshVersion]);

  async function changeAssociation(contact: CrmContact, linked: boolean) {
    if (
      mutationInProgress.current ||
      (linked && (linkedIds.has(contact.id) || linkedSearchIds.has(contact.id)))
    ) {
      return;
    }
    mutationInProgress.current = true;
    setPendingContactId(contact.id);
    setMutationError(null);
    setNotice(null);
    try {
      await updateCrmContactLeadLink(contact.id, {
        expected_revision: contact.revision,
        lead_id: leadId,
        linked,
      });
      startRefresh();
      setNotice(
        linked
          ? `${contact.display_name} linked to this Lead.`
          : `${contact.display_name} unlinked from this Lead.`,
      );
      setRefreshVersion((version) => version + 1);
    } catch (error) {
      setMutationError(mutationErrorMessage(error));
      if (error instanceof ApiError && error.status === 409) {
        startRefresh();
        setRefreshVersion((version) => version + 1);
      }
    } finally {
      mutationInProgress.current = false;
      setPendingContactId(null);
    }
  }

  function updateSearch(value: string) {
    setSearch(value);
    setSearchOffset(0);
    setMutationError(null);
    setNotice(null);
    if (value.trim()) {
      setSearchLoading(true);
      setSearchError(null);
    } else {
      setCandidates({ items: [], total: 0 });
      setSearchLoading(false);
      setSearchError(null);
    }
  }

  function startRefresh() {
    setLinkedLoading(true);
    setLinkedError(null);
    if (normalizedSearch) {
      setSearchLoading(true);
      setSearchError(null);
    }
  }

  function goToLinkedOffset(offset: number) {
    setLinkedLoading(true);
    setLinkedError(null);
    setLinkedOffset(offset);
  }

  function goToSearchOffset(offset: number) {
    setSearchLoading(true);
    setSearchError(null);
    setSearchOffset(offset);
  }

  return (
    <section
      className="border-border grid gap-4 border-t pt-5"
      aria-labelledby="crm-contact-associations-title"
    >
      <div>
        <h3 id="crm-contact-associations-title" className="text-sm font-medium">
          Linked CRM Contacts
        </h3>
        <p className="text-muted-foreground mt-1 text-xs">
          Link existing CRM Contacts without changing this Lead&apos;s details.
        </p>
      </div>

      {mutationError ? (
        <p className="text-danger-text text-sm" role="alert">
          {mutationError}
        </p>
      ) : null}
      {notice ? (
        <p className="text-sm" role="status">
          {notice}
        </p>
      ) : null}

      <div aria-busy={linkedLoading}>
        <h4 className="text-muted-foreground text-xs font-medium">
          Linked Contacts ({linkedPage.total})
        </h4>
        {linkedLoading ? (
          <p className="text-muted-foreground mt-2 text-sm" role="status">
            Loading linked Contacts…
          </p>
        ) : linkedError ? (
          <div className="mt-2 grid gap-2">
            <p className="text-danger-text text-sm" role="alert">
              {linkedError}
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                startRefresh();
                setRefreshVersion((version) => version + 1);
              }}
            >
              Retry linked Contacts
            </Button>
          </div>
        ) : linkedPage.items.length === 0 ? (
          <p className="text-muted-foreground mt-2 text-sm">
            No CRM Contacts are linked to this Lead yet.
          </p>
        ) : (
          <ul className="mt-2 grid gap-2">
            {linkedPage.items.map((contact) => {
              const archived = contact.archived_at !== null;
              return (
                <li
                  key={contact.id}
                  className="border-border flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium">
                      {contact.display_name}
                    </p>
                    <div className="text-muted-foreground mt-1 grid gap-1 text-xs">
                      {contact.job_title ? <p>{contact.job_title}</p> : null}
                      {contact.email ? (
                        <a
                          className="hover:text-foreground w-fit underline-offset-4 hover:underline"
                          href={`mailto:${contact.email}`}
                        >
                          {contact.email}
                        </a>
                      ) : null}
                      {contact.phone ? (
                        <a
                          className="hover:text-foreground w-fit underline-offset-4 hover:underline"
                          href={`tel:${contact.phone}`}
                        >
                          {contact.phone}
                        </a>
                      ) : null}
                      {contact.mobile ? (
                        <a
                          className="hover:text-foreground w-fit underline-offset-4 hover:underline"
                          href={`tel:${contact.mobile}`}
                        >
                          Mobile: {contact.mobile}
                        </a>
                      ) : null}
                      {contact.linkedin_url ? (
                        <p className="break-all">
                          LinkedIn: {contact.linkedin_url}
                        </p>
                      ) : null}
                      {contact.company_id ? (
                        <p>
                          Company:{" "}
                          {companyNames[contact.company_id] ??
                            (companyErrors[contact.company_id]
                              ? "Details unavailable"
                              : "Loading…")}
                        </p>
                      ) : null}
                      {archived ? (
                        <p className="text-warning-text">
                          Archived — restore this Contact before changing its
                          links.
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={archived || pendingContactId !== null}
                    onClick={() => void changeAssociation(contact, false)}
                    aria-label={`Unlink ${contact.display_name}`}
                  >
                    {pendingContactId === contact.id ? "Updating…" : "Unlink"}
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        {!linkedLoading && !linkedError && linkedPage.total > PAGE_SIZE ? (
          <div className="mt-3 flex items-center justify-between">
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={linkedOffset === 0}
              onClick={() =>
                goToLinkedOffset(Math.max(0, linkedOffset - PAGE_SIZE))
              }
            >
              Previous linked Contacts
            </Button>
            <span className="text-muted-foreground text-xs">
              {linkedOffset + 1}–
              {Math.min(linkedOffset + PAGE_SIZE, linkedPage.total)} of{" "}
              {linkedPage.total}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={linkedOffset + PAGE_SIZE >= linkedPage.total}
              onClick={() => goToLinkedOffset(linkedOffset + PAGE_SIZE)}
            >
              Next linked Contacts
            </Button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-2">
        <label
          htmlFor={`crm-contact-search-${leadId}`}
          className="text-muted-foreground text-xs font-medium"
        >
          Search CRM Contacts
        </label>
        <Input
          id={`crm-contact-search-${leadId}`}
          type="search"
          value={search}
          onChange={(event) => updateSearch(event.currentTarget.value)}
          placeholder="Search by name, email or phone"
          autoComplete="off"
        />
        {normalizedSearch ? (
          <div aria-busy={searchLoading}>
            {searchLoading ? (
              <p className="text-muted-foreground text-sm" role="status">
                Searching Contacts…
              </p>
            ) : searchError ? (
              <div className="grid gap-2">
                <p className="text-danger-text text-sm" role="alert">
                  {searchError}
                </p>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    startRefresh();
                    setRefreshVersion((version) => version + 1);
                  }}
                >
                  Retry Contact search
                </Button>
              </div>
            ) : (
              <>
                {availableCandidates.length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    {candidates.total > 0
                      ? "No unlinked Contacts on this search page."
                      : "No matching Contacts found."}
                  </p>
                ) : (
                  <ul className="grid gap-2">
                    {availableCandidates.map((contact) => (
                      <li
                        key={contact.id}
                        className="border-border flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium">
                            {contact.display_name}
                          </p>
                          <p className="text-muted-foreground mt-1 text-xs">
                            {[
                              contact.job_title,
                              contact.email,
                              contact.phone,
                              contact.mobile,
                            ]
                              .filter(Boolean)
                              .join(" · ") || "No additional details"}
                          </p>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          disabled={pendingContactId !== null}
                          onClick={() => void changeAssociation(contact, true)}
                          aria-label={`Link ${contact.display_name}`}
                        >
                          {pendingContactId === contact.id
                            ? "Updating…"
                            : "Link"}
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
                {candidates.total > PAGE_SIZE ? (
                  <div className="mt-3 flex items-center justify-between">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={searchOffset === 0}
                      onClick={() =>
                        goToSearchOffset(Math.max(0, searchOffset - PAGE_SIZE))
                      }
                    >
                      Previous search results
                    </Button>
                    <span className="text-muted-foreground text-xs">
                      {searchOffset + 1}–
                      {Math.min(searchOffset + PAGE_SIZE, candidates.total)} of{" "}
                      {candidates.total}
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={searchOffset + PAGE_SIZE >= candidates.total}
                      onClick={() => goToSearchOffset(searchOffset + PAGE_SIZE)}
                    >
                      Next search results
                    </Button>
                  </div>
                ) : null}
              </>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground text-xs">
            Search for a Contact to link.
          </p>
        )}
      </div>
    </section>
  );
}
