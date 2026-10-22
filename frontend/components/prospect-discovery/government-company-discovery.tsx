"use client";

import { AlertCircle, Building2, LoaderCircle, Search } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import { ApiError } from "@/lib/api/client";
import { searchGovernmentCompanies } from "@/lib/api/prospect-discovery";
import { getRuntimeConfiguration } from "@/lib/api/runtime";
import type {
  GovernmentCompanyDiscoveryResponse,
  NormalizedCompanyRecord,
  RuntimeConfiguration,
} from "@/types/api";

const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

function isPositiveSafeInteger(value: number | undefined): value is number {
  return value !== undefined && Number.isSafeInteger(value) && value > 0;
}

function isNonNegativeSafeInteger(value: number | undefined): value is number {
  return value !== undefined && Number.isSafeInteger(value) && value >= 0;
}

function safeGovernmentSearchError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Government company discovery could not be reached. Try again later.";
  }
  if (error.status === 401)
    return "Your session has expired. Sign in again to continue.";
  if (error.status === 403)
    return "You do not have access to this organization’s discovery workspace.";
  if (error.status === 429) {
    return "The organization’s discovery usage limit has been reached. Try again later.";
  }
  if (error.status === 503) {
    return "Government company discovery is unavailable. Check with your administrator.";
  }
  if (error.status === 400 || error.status === 422) {
    return "The government discovery request was rejected. Check the state code or page settings.";
  }
  return "Government company discovery could not be completed. Try again.";
}

function companyNameField(
  record: Record<string, string | number | boolean | null>,
) {
  return Object.keys(record).find(
    (key) => key.toLowerCase().replace(/[^a-z0-9]/g, "") === "companyname",
  );
}

function displayRecordValue(value: string | number | boolean | null): string {
  if (value === null) return "null";
  return String(value);
}

function NormalizedRecord({
  record,
}: {
  record: NormalizedCompanyRecord;
}) {
  const fields: [string, string | number | boolean | null][] = [
    ["Company name", record.company_name],
    ["CIN", record.cin],
    ["Status", record.company_status],
    ["Class", record.company_class],
    ["Category", record.company_category],
    ["Sub-category", record.company_sub_category],
    ["Authorized capital", record.authorized_capital],
    ["Paid-up capital", record.paid_up_capital],
    ["Number of members", record.number_of_members],
    ["Date of incorporation", record.date_of_incorporation],
    ["Registered address", record.registered_address],
    ["State code", record.company_state_code],
    ["Registrar of Companies", record.registrar_of_companies],
    ["Principal business activity", record.principal_business_activity],
    ["Industrial classification code", record.industrial_classification_code],
  ];

  return (
    <section
      aria-label="Normalized company record"
      className="border-border grid gap-2 rounded-md border border-dashed p-3 text-sm"
    >
      <h4 className="font-medium">Normalized source fields</h4>
      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[minmax(8rem,0.25fr)_1fr]">
        {fields
          .filter(([, value]) => value !== null)
          .map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="break-words">{displayRecordValue(value)}</dd>
            </div>
          ))}
      </dl>
      <p className="text-muted-foreground text-xs">
        {record.attribution.attribution} Retrieved at {record.retrieved_at}.
      </p>
    </section>
  );
}

function GovernmentRecords({
  response,
}: {
  response: GovernmentCompanyDiscoveryResponse;
}) {
  if (response.items.length === 0) {
    return (
      <div className="border-border grid justify-items-center gap-2 rounded-lg border border-dashed px-5 py-8 text-center">
        <Search className="text-muted-foreground size-5" aria-hidden="true" />
        <h3 className="text-sm font-semibold">
          No government company records found
        </h3>
        <p className="text-muted-foreground text-sm">
          No records were returned for this state code and page.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3" aria-label="Government company records">
      {response.items.map((record, index) => {
        const normalizedRecord = response.normalized_items?.[index];
        const nameKey = companyNameField(record);
        const nameValue = nameKey ? record[nameKey] : null;
        const name =
          typeof nameValue === "string" && nameValue.trim()
            ? nameValue
            : "Company name not provided by source";
        const fields = Object.entries(record).filter(
          ([key]) => key !== nameKey,
        );

        return (
          <article
            key={`${String(record.CIN ?? record.cin ?? index)}-${index}`}
            className="border-border bg-card grid gap-3 rounded-lg border p-4 sm:p-5"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 gap-3">
                <span className="bg-muted text-muted-foreground grid size-9 shrink-0 place-items-center rounded-md">
                  <Building2 className="size-4" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <h3 className="text-base font-semibold">{name}</h3>
                </div>
              </div>
              <StatusBadge status="pending" label="Government sourced" />
            </div>
            {fields.length > 0 ? (
              <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[minmax(8rem,0.25fr)_1fr]">
                {fields.map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="text-muted-foreground">{key}</dt>
                    <dd className="break-words">{displayRecordValue(value)}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            {normalizedRecord ? (
              <NormalizedRecord record={normalizedRecord} />
            ) : null}
          </article>
        );
      })}
    </div>
  );
}

export function GovernmentCompanyDiscovery() {
  const [availability, setAvailability] = useState<RuntimeConfiguration | null>(
    null,
  );
  const [availabilityError, setAvailabilityError] = useState(false);
  const [isCheckingAvailability, setIsCheckingAvailability] = useState(true);
  const [stateCode, setStateCode] = useState("");
  const [pageSize, setPageSize] = useState(20);
  const [offset, setOffset] = useState(0);
  const [previousOffsets, setPreviousOffsets] = useState<number[]>([]);
  const [response, setResponse] =
    useState<GovernmentCompanyDiscoveryResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const requestSequence = useRef(0);

  useEffect(() => {
    let active = true;
    void getRuntimeConfiguration()
      .then((configuration) => {
        if (!active) return;
        setAvailability(configuration);
        setIsCheckingAvailability(false);
        if (
          isPositiveSafeInteger(
            configuration.government_company_discovery_max_page_size,
          )
        ) {
          setPageSize(
            Math.min(
              20,
              configuration.government_company_discovery_max_page_size,
            ),
          );
        }
      })
      .catch(() => {
        if (!active) return;
        setAvailabilityError(true);
        setIsCheckingAvailability(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const configuredPageSizeMaximum =
    availability?.government_company_discovery_max_page_size;
  const configuredOffsetMaximum =
    availability?.government_company_discovery_max_offset;
  const pageSizeMaximum = isPositiveSafeInteger(configuredPageSizeMaximum)
    ? configuredPageSizeMaximum
    : 0;
  const offsetMaximum = isNonNegativeSafeInteger(configuredOffsetMaximum)
    ? configuredOffsetMaximum
    : 0;
  const hasValidBounds =
    pageSizeMaximum > 0 && isNonNegativeSafeInteger(configuredOffsetMaximum);
  const isAvailable =
    availability?.government_company_discovery_available === true &&
    hasValidBounds;
  const pageSizeOptions = hasValidBounds
    ? PAGE_SIZE_OPTIONS.filter((size) => size <= pageSizeMaximum)
    : [];
  if (pageSizeMaximum > 0 && !pageSizeOptions.includes(pageSizeMaximum)) {
    pageSizeOptions.push(pageSizeMaximum);
    pageSizeOptions.sort((left, right) => left - right);
  }
  const selectedPageSize = pageSizeOptions.includes(pageSize)
    ? pageSize
    : (pageSizeOptions[0] ?? "");

  async function searchAt(nextOffset: number, resetHistory: boolean) {
    if (
      !isAvailable ||
      isSearching ||
      !stateCode.trim() ||
      !pageSizeOptions.includes(pageSize) ||
      nextOffset < 0 ||
      nextOffset > offsetMaximum
    ) {
      return;
    }
    const sequence = ++requestSequence.current;
    setIsSearching(true);
    setSearchError(null);
    setResponse(null);
    if (resetHistory) setPreviousOffsets([]);
    setOffset(nextOffset);
    try {
      const result = await searchGovernmentCompanies({
        state_code: stateCode.trim(),
        offset: nextOffset,
        page_size: pageSize,
      });
      if (sequence === requestSequence.current) setResponse(result);
    } catch (error) {
      if (sequence === requestSequence.current) {
        setSearchError(safeGovernmentSearchError(error));
      }
    } finally {
      if (sequence === requestSequence.current) setIsSearching(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (stateCode.trim().length < 1 || stateCode.trim().length > 10) {
      setSearchError("Enter a state code of 1 to 10 characters.");
      setResponse(null);
      return;
    }
    void searchAt(0, true);
  }

  function loadNextPage() {
    if (response?.next_offset === null || response?.next_offset === undefined)
      return;
    setPreviousOffsets((current) => [...current, offset]);
    void searchAt(response.next_offset, false);
  }

  function loadPreviousPage() {
    const previousOffset = previousOffsets.at(-1);
    if (previousOffset === undefined) return;
    setPreviousOffsets((current) => current.slice(0, -1));
    void searchAt(previousOffset, false);
  }

  const pageEnd =
    response === null ? 0 : response.offset + response.items.length;

  return (
    <section
      aria-labelledby="government-discovery-title"
      className="border-border grid gap-4 rounded-lg border p-4 sm:p-5"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 id="government-discovery-title" className="text-sm font-semibold">
            Government Company Discovery
          </h2>
          <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
            Search the Registrars of Companies company master data. Results are
            read-only and are not saved to your CRM.
          </p>
        </div>
        <StatusBadge
          status={isAvailable ? "active" : "paused"}
          label={isAvailable ? "Backend enabled" : "Unavailable"}
        />
      </div>

      <aside
        className="border-warning/40 bg-warning/5 rounded-lg border px-4 py-3 text-sm leading-5"
        aria-label="Government data licensing notice"
      >
        <strong>Licence and API quota clarification is pending.</strong> API
        availability does not grant commercial-use permission. Government
        records are source data; no missing information is inferred.
      </aside>

      {isCheckingAvailability ? (
        <p
          role="status"
          className="text-muted-foreground flex items-center gap-2 text-sm"
        >
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          Checking government discovery availability…
        </p>
      ) : null}
      {availabilityError ? (
        <p role="status" className="text-muted-foreground text-sm">
          Availability could not be confirmed. Government discovery remains
          unavailable.
        </p>
      ) : null}
      {!isCheckingAvailability && !availabilityError && !isAvailable ? (
        <p role="status" className="text-muted-foreground text-sm">
          {availability?.government_company_discovery_available === true &&
          !hasValidBounds
            ? "The server returned invalid discovery limits. Government discovery remains unavailable."
            : "This provider is disabled or not configured by the server administrator."}
        </p>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className="grid gap-3 sm:grid-cols-[1fr_10rem_auto] sm:items-end"
      >
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">CompanyStateCode</span>
          <input
            type="text"
            maxLength={10}
            value={stateCode}
            disabled={!isAvailable || isSearching}
            onChange={(event) => {
              setStateCode(event.target.value);
              setResponse(null);
              setSearchError(null);
            }}
            className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
          />
        </label>
        <label className="grid gap-1.5 text-sm">
          <span className="font-medium">Records per page</span>
          <select
            value={selectedPageSize}
            disabled={
              !isAvailable || isSearching || pageSizeOptions.length === 0
            }
            onChange={(event) => {
              const selectedSize = Number(event.target.value);
              if (pageSizeOptions.includes(selectedSize)) {
                setPageSize(selectedSize);
              }
              setResponse(null);
              setPreviousOffsets([]);
            }}
            className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
        <Button
          type="submit"
          disabled={!isAvailable || isSearching || !stateCode.trim()}
          className="gap-2"
        >
          {isSearching ? (
            <>
              <LoaderCircle
                className="size-4 animate-spin"
                aria-hidden="true"
              />
              Searching…
            </>
          ) : (
            <>
              <Search className="size-4" aria-hidden="true" />
              Search government records
            </>
          )}
        </Button>
      </form>

      {isSearching ? (
        <p
          role="status"
          className="text-muted-foreground flex items-center gap-2 text-sm"
        >
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          Loading government company records…
        </p>
      ) : null}
      {searchError ? (
        <p
          role="alert"
          className="text-danger-text flex items-start gap-2 text-sm"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {searchError}
        </p>
      ) : null}

      {response ? (
        <div className="grid gap-4">
          <div className="border-border flex flex-col gap-2 border-y py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
            <p>
              Showing {response.items.length === 0 ? 0 : response.offset + 1}–
              {pageEnd}
              {response.total === null
                ? ""
                : ` of ${response.total.toLocaleString()}`}
            </p>
            <p className="text-muted-foreground">
              Source: {response.attribution.dataset} ·{" "}
              {response.attribution.provider}
            </p>
          </div>
          <GovernmentRecords response={response} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-muted-foreground text-xs">
              {response.attribution.attribution}
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={isSearching || previousOffsets.length === 0}
                onClick={loadPreviousPage}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={
                  isSearching ||
                  !response.has_more ||
                  response.next_offset === null ||
                  response.next_offset > offsetMaximum
                }
                onClick={loadNextPage}
              >
                Next
              </Button>
            </div>
          </div>
          <a
            className="text-primary w-fit text-xs underline underline-offset-4"
            href={response.attribution.endpoint}
            target="_blank"
            rel="noreferrer"
          >
            View dataset resource
          </a>
        </div>
      ) : null}
    </section>
  );
}
