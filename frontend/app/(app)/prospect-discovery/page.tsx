"use client";

import {
  AlertCircle,
  ArrowRight,
  Building2,
  LoaderCircle,
  RotateCcw,
  Search,
  Sparkles,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { searchProspects } from "@/lib/api/prospect-discovery";
import type {
  ProspectDiscoverySearchRequest,
  ProspectDiscoverySearchResponse,
} from "@/types/api";

const INDUSTRIES = [
  "Financial Services",
  "Healthcare",
  "Manufacturing",
  "Professional Services",
  "Software",
] as const;

const REGIONS_BY_COUNTRY: Record<string, readonly string[]> = {
  Australia: ["New South Wales", "Victoria"],
  Canada: ["British Columbia", "Ontario"],
  India: ["Karnataka", "Maharashtra"],
  "United Kingdom": ["England", "Scotland"],
  "United States": ["California", "New York", "Texas"],
};

const COUNTRIES = Object.keys(REGIONS_BY_COUNTRY);
const PAGE_SIZES = [5, 10, 20, 25] as const;

type SearchFilters = {
  industry: string;
  country: string;
  region: string;
  minimum_employees: string;
  maximum_employees: string;
  page_size: number;
};
type FilterErrors = Partial<Record<"minimum_employees" | "maximum_employees", string>>;

const INITIAL_FILTERS: SearchFilters = {
  industry: "",
  country: "",
  region: "",
  minimum_employees: "",
  maximum_employees: "",
  page_size: 10,
};

function safeSearchError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Discovery could not be reached. Check your connection and try again.";
  }
  if (error.status === 401) return "Your session has expired. Sign in again to search.";
  if (error.status === 403) return "You do not have access to this organization’s discovery workspace.";
  if (error.status === 429) {
    return "The organization’s discovery usage limit has been reached. Try again later.";
  }
  if (error.status === 503) return "Synthetic discovery is temporarily unavailable. Try again shortly.";
  if (error.status === 400 || error.status === 422) {
    return "Some search filters are invalid or the page cursor has expired. Review the filters and search again.";
  }
  return "Discovery could not be completed. Try again.";
}

function parseEmployeeCount(value: string): number | undefined {
  if (value === "") return undefined;
  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : undefined;
}

function buildRequest(filters: SearchFilters): ProspectDiscoverySearchRequest {
  const minimum = parseEmployeeCount(filters.minimum_employees);
  const maximum = parseEmployeeCount(filters.maximum_employees);
  return {
    ...(filters.industry ? { industry: filters.industry } : {}),
    ...(filters.country ? { country: filters.country } : {}),
    ...(filters.region ? { region: filters.region } : {}),
    ...(minimum !== undefined ? { minimum_employees: minimum } : {}),
    ...(maximum !== undefined ? { maximum_employees: maximum } : {}),
    page_size: filters.page_size,
  };
}

function validateFilters(filters: SearchFilters): FilterErrors {
  const errors: FilterErrors = {};
  const minimum = parseEmployeeCount(filters.minimum_employees);
  const maximum = parseEmployeeCount(filters.maximum_employees);
  if (filters.minimum_employees !== "" && minimum === undefined) {
    errors.minimum_employees = "Enter a whole employee count.";
  } else if (minimum !== undefined && (minimum < 0 || minimum > 1_000_000)) {
    errors.minimum_employees = "Enter a value from 0 to 1,000,000.";
  }
  if (filters.maximum_employees !== "" && maximum === undefined) {
    errors.maximum_employees = "Enter a whole employee count.";
  } else if (maximum !== undefined && (maximum < 0 || maximum > 1_000_000)) {
    errors.maximum_employees = "Enter a value from 0 to 1,000,000.";
  }
  if (
    minimum !== undefined &&
    maximum !== undefined &&
    minimum > maximum
  ) {
    errors.minimum_employees = "Minimum employees cannot exceed maximum.";
    errors.maximum_employees = "Maximum employees must be at least the minimum.";
  }
  return errors;
}

function SearchSkeleton() {
  return (
    <div role="status" aria-label="Loading synthetic businesses" className="grid gap-3">
      <span className="text-muted-foreground flex items-center gap-2 text-sm">
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        Searching synthetic businesses…
      </span>
      {[0, 1, 2].map((item) => (
        <div
          key={item}
          aria-hidden="true"
          className="border-border bg-muted/40 h-24 animate-pulse rounded-lg border"
        />
      ))}
    </div>
  );
}

function BusinessResults({
  response,
}: {
  response: ProspectDiscoverySearchResponse;
}) {
  if (response.items.length === 0) {
    return (
      <div className="border-border grid justify-items-center gap-2 rounded-lg border border-dashed px-5 py-10 text-center">
        <Search className="text-muted-foreground size-5" aria-hidden="true" />
        <h2 className="text-sm font-semibold">No synthetic businesses matched</h2>
        <p className="text-muted-foreground max-w-lg text-sm">
          Try widening the filters. The fixed synthetic dataset is intentionally
          limited and does not represent comprehensive real-world coverage.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-3" aria-label="Synthetic business results">
      {response.items.map((business) => (
        <article
          key={`${business.name}-${business.country}-${business.region}`}
          className="border-border bg-card grid gap-3 rounded-lg border p-4 sm:p-5"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 gap-3">
              <span className="bg-muted text-muted-foreground grid size-9 shrink-0 place-items-center rounded-md">
                <Building2 className="size-4" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 className="text-base font-semibold">{business.name}</h2>
                <p className="text-muted-foreground mt-1 text-sm">
                  {business.industry} · {business.region}, {business.country}
                </p>
              </div>
            </div>
            <span className="bg-warning/15 text-warning-text inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium">
              <Sparkles className="size-3.5" aria-hidden="true" />
              Synthetic · unverified
            </span>
          </div>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[minmax(8rem,0.25fr)_1fr]">
            <dt className="text-muted-foreground">Employee count</dt>
            <dd>{business.employee_count.toLocaleString()}</dd>
            <dt className="text-muted-foreground">Description</dt>
            <dd>{business.description}</dd>
            <dt className="text-muted-foreground">Search match</dt>
            <dd>
              <ul className="grid gap-1">
                {business.match_explanations.map((explanation) => (
                  <li key={explanation}>{explanation}</li>
                ))}
              </ul>
              <p className="text-muted-foreground mt-2 text-xs">
                Filter explanations only; no formal CompanyProspect ICP fit score
                is available for these ephemeral results.
              </p>
            </dd>
          </dl>
        </article>
      ))}
    </div>
  );
}

export default function ProspectDiscoveryPage() {
  const [filters, setFilters] = useState<SearchFilters>(INITIAL_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<SearchFilters | null>(null);
  const [response, setResponse] = useState<ProspectDiscoverySearchResponse | null>(null);
  const [errors, setErrors] = useState<FilterErrors>({});
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const requestSequence = useRef(0);
  const requestInFlight = useRef(false);

  async function executeSearch(
    request: ProspectDiscoverySearchRequest,
    nextFilters: SearchFilters,
  ) {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    const sequence = ++requestSequence.current;
    setIsLoading(true);
    setSearchError(null);
    setResponse(null);
    setAppliedFilters(nextFilters);
    try {
      const result = await searchProspects(request);
      if (sequence === requestSequence.current) setResponse(result);
    } catch (error) {
      if (sequence === requestSequence.current) setSearchError(safeSearchError(error));
    } finally {
      if (sequence === requestSequence.current) {
        setIsLoading(false);
        requestInFlight.current = false;
      }
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (requestInFlight.current) return;
    const nextErrors = validateFilters(filters);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;
    void executeSearch(buildRequest(filters), filters);
  }

  function updateFilters(update: Partial<SearchFilters>) {
    setFilters((current) => ({ ...current, ...update }));
    setErrors({});
    setAppliedFilters(null);
    setResponse(null);
    setSearchError(null);
  }

  function resetFilters() {
    requestSequence.current += 1;
    requestInFlight.current = false;
    setFilters(INITIAL_FILTERS);
    setAppliedFilters(null);
    setResponse(null);
    setErrors({});
    setSearchError(null);
    setIsLoading(false);
  }

  function loadNextPage() {
    if (!response?.next_cursor || !appliedFilters || requestInFlight.current) return;
    void executeSearch(
      { ...buildRequest(appliedFilters), cursor: response.next_cursor },
      appliedFilters,
    );
  }

  const resultCount = response?.items.length ?? 0;

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Discovery Workspace"
        description="Explore a small, fixed set of synthetic business examples using your discovery filters."
        titleBadge={
          <span className="bg-warning/15 text-warning-text rounded-full px-2.5 py-1 text-xs font-medium">
            Synthetic data only
          </span>
        }
      />

      <aside
        className="border-warning/40 bg-warning/5 flex gap-3 rounded-lg border px-4 py-3"
        aria-label="Synthetic data notice"
      >
        <Sparkles className="text-warning-text mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <p className="text-sm leading-5">
          <strong>Synthetic, unverified examples.</strong> These records are
          generated from a fixed demo dataset, are not verified real companies,
          and are not saved to your CRM. No live business-data provider is
          connected.
        </p>
      </aside>

      <section
        aria-labelledby="prospect-import-title"
        className="border-border flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"
      >
        <div>
          <h2 id="prospect-import-title" className="text-sm font-semibold">
            Company prospect import
          </h2>
          <p className="text-muted-foreground mt-1 max-w-3xl text-sm">
            Import is unavailable while discovery uses synthetic, unverified
            data. No discovery results can be saved as genuine company
            prospects. Import can be enabled only after an explicitly approved
            source provides eligible verified records.
          </p>
        </div>
        <Button type="button" variant="outline" disabled aria-describedby="prospect-import-title">
          Import unavailable
        </Button>
      </section>

      <section aria-labelledby="search-filters-title" className="border-border rounded-lg border p-4 sm:p-5">
        <div className="mb-4">
          <h2 id="search-filters-title" className="text-sm font-semibold">
            Search filters
          </h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Filters are limited to the fields supported by synthetic discovery.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="grid gap-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Industry</span>
              <select
                value={filters.industry}
                disabled={isLoading}
                onChange={(event) => updateFilters({ industry: event.target.value })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2"
              >
                <option value="">All supported industries</option>
                {INDUSTRIES.map((industry) => (
                  <option key={industry} value={industry}>{industry}</option>
                ))}
              </select>
            </label>
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Country</span>
              <select
                value={filters.country}
                disabled={isLoading}
                onChange={(event) => updateFilters({ country: event.target.value, region: "" })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2"
              >
                <option value="">All supported countries</option>
                {COUNTRIES.map((country) => (
                  <option key={country} value={country}>{country}</option>
                ))}
              </select>
            </label>
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Region</span>
              <select
                value={filters.region}
                disabled={!filters.country || isLoading}
                onChange={(event) => updateFilters({ region: event.target.value })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <option value="">All supported regions</option>
                {(REGIONS_BY_COUNTRY[filters.country] ?? []).map((region) => (
                  <option key={region} value={region}>{region}</option>
                ))}
              </select>
              <span className="text-muted-foreground text-xs">Select a country first.</span>
            </label>
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Minimum employees</span>
              <input
                type="number"
                min={0}
                max={1_000_000}
                step={1}
                inputMode="numeric"
                value={filters.minimum_employees}
                disabled={isLoading}
                aria-invalid={Boolean(errors.minimum_employees)}
                aria-describedby={errors.minimum_employees ? "minimum-employees-error" : undefined}
                onChange={(event) => updateFilters({ minimum_employees: event.target.value })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2 aria-invalid:border-destructive"
              />
              {errors.minimum_employees ? (
                <span id="minimum-employees-error" className="text-danger-text text-xs" role="alert">
                  {errors.minimum_employees}
                </span>
              ) : null}
            </label>
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Maximum employees</span>
              <input
                type="number"
                min={0}
                max={1_000_000}
                step={1}
                inputMode="numeric"
                value={filters.maximum_employees}
                disabled={isLoading}
                aria-invalid={Boolean(errors.maximum_employees)}
                aria-describedby={errors.maximum_employees ? "maximum-employees-error" : undefined}
                onChange={(event) => updateFilters({ maximum_employees: event.target.value })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2 aria-invalid:border-destructive"
              />
              {errors.maximum_employees ? (
                <span id="maximum-employees-error" className="text-danger-text text-xs" role="alert">
                  {errors.maximum_employees}
                </span>
              ) : null}
            </label>
            <label className="grid content-start gap-1.5 text-sm">
              <span className="font-medium">Results per page</span>
              <select
                value={filters.page_size}
                disabled={isLoading}
                onChange={(event) => updateFilters({ page_size: Number(event.target.value) })}
                className="border-input bg-background focus-visible:ring-ring h-9 rounded-md border px-3 outline-none focus-visible:ring-2"
              >
                {PAGE_SIZES.map((size) => (
                  <option key={size} value={size}>{size} results</option>
                ))}
              </select>
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <Search aria-hidden="true" />
              )}
              {isLoading ? "Searching…" : "Search businesses"}
            </Button>
            <Button type="button" variant="outline" onClick={resetFilters}>
              <RotateCcw aria-hidden="true" />
              Reset filters
            </Button>
          </div>
        </form>
      </section>

      {searchError ? (
        <div role="alert" className="border-destructive/40 bg-destructive/5 flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3">
          <p className="text-danger-text flex items-center gap-2 text-sm">
            <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
            {searchError}
          </p>
          {appliedFilters ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => void executeSearch(buildRequest(appliedFilters), appliedFilters)}
              disabled={isLoading}
            >
              Retry search
            </Button>
          ) : null}
        </div>
      ) : null}

      {isLoading ? <SearchSkeleton /> : null}

      {response && !isLoading ? (
        <section aria-labelledby="search-results-title" className="grid gap-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 id="search-results-title" className="text-sm font-semibold">
                Search results
              </h2>
              <p className="text-muted-foreground mt-1 text-sm" aria-live="polite">
                {resultCount} synthetic {resultCount === 1 ? "business" : "businesses"} on this page
                {response.has_more ? " · More results available" : " · End of results"}
              </p>
            </div>
            <span className="text-muted-foreground text-xs">
              Match explanations are filter matches, not formal ICP fit scores.
            </span>
          </div>
          <BusinessResults response={response} />
          {response.has_more && response.next_cursor ? (
            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={loadNextPage} disabled={isLoading}>
                Next page
                <ArrowRight aria-hidden="true" />
              </Button>
            </div>
          ) : null}
        </section>
      ) : null}

      {!response && !isLoading && !searchError ? (
        <div className="border-border text-muted-foreground rounded-lg border border-dashed px-5 py-8 text-center text-sm">
          Choose any supported filters and search to explore the synthetic demo dataset.
        </div>
      ) : null}
    </div>
  );
}
