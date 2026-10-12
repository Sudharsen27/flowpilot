"use client";

import { CalendarDays, Code2, Database, MessageSquare } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { FilterBar } from "@/components/forms/filter-bar";
import { Label } from "@/components/forms/label";
import { SearchInput } from "@/components/forms/search-input";
import { Select } from "@/components/forms/select";
import { IntegrationStatusBadge } from "@/components/integrations/integration-status-badge";
import type { IntegrationStatus } from "@/components/integrations/integration-status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type IntegrationCategory = "crm" | "communication" | "calendar" | "developer";

type IntegrationConcept = {
  id: string;
  name: string;
  category: IntegrationCategory;
  description: string;
  status: IntegrationStatus;
  setupNote?: string;
};

const categoryPresentation = {
  crm: { label: "CRM", icon: Database },
  communication: { label: "Communication", icon: MessageSquare },
  calendar: { label: "Calendar", icon: CalendarDays },
  developer: { label: "Automation / developer", icon: Code2 },
} as const;

const DEFAULT_SETUP_NOTE =
  "Needs a FlowPilot app registration and credentials with this provider before it can be connected. Until then, use a webhook to send events to it through a tool like Zapier or Make.";

const integrationConcepts: IntegrationConcept[] = [
  {
    id: "salesforce",
    name: "Salesforce",
    category: "crm",
    description: "Sync leads and outcomes with Salesforce.",
    status: "needs-setup",
  },
  {
    id: "hubspot",
    name: "HubSpot",
    category: "crm",
    description: "Sync leads and outcomes with HubSpot.",
    status: "needs-setup",
  },
  {
    id: "pipedrive",
    name: "Pipedrive",
    category: "crm",
    description: "Sync leads and deals with Pipedrive.",
    status: "needs-setup",
  },
  {
    id: "gmail",
    name: "Gmail",
    category: "communication",
    description: "Send and receive lead email from a Gmail mailbox.",
    status: "needs-setup",
  },
  {
    id: "outlook",
    name: "Outlook",
    category: "communication",
    description: "Send and receive lead email from an Outlook mailbox.",
    status: "needs-setup",
  },
  {
    id: "slack",
    name: "Slack",
    category: "communication",
    description: "Post lead alerts to a Slack channel.",
    status: "needs-setup",
  },
  {
    id: "whatsapp",
    name: "WhatsApp",
    category: "communication",
    description: "Reply to leads on WhatsApp Business.",
    status: "needs-setup",
  },
  {
    id: "google-calendar",
    name: "Google Calendar",
    category: "calendar",
    description: "Book meetings and count appointments from Google Calendar.",
    status: "needs-setup",
  },
  {
    id: "microsoft-outlook-calendar",
    name: "Microsoft Outlook Calendar",
    category: "calendar",
    description: "Book meetings and count appointments from Outlook Calendar.",
    status: "needs-setup",
  },
  {
    id: "rest-api",
    name: "REST API",
    category: "developer",
    description: "Read and write FlowPilot data from your own systems with an API key.",
    status: "needs-setup",
    setupNote:
      "API keys for FlowPilot are not available yet. Use a webhook to receive events today.",
  },
];

export function IntegrationCatalog() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  const filteredIntegrations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return integrationConcepts.filter((integration) => {
      const matchesQuery =
        normalizedQuery === "" ||
        integration.name.toLowerCase().includes(normalizedQuery) ||
        categoryPresentation[integration.category].label
          .toLowerCase()
          .includes(normalizedQuery);
      const matchesCategory =
        category === "all" || integration.category === category;
      return matchesQuery && matchesCategory;
    });
  }, [category, query]);

  const activeFilterCount = [
    query.trim() !== "",
    category !== "all",
  ].filter(Boolean).length;

  function clearFilters() {
    setQuery("");
    setCategory("all");
  }

  const resultLabel = `${filteredIntegrations.length} integration${
    filteredIntegrations.length === 1 ? "" : "s"
  }`;

  return (
    <div className="grid gap-4">
      <div className="border-border bg-surface-subtle grid gap-2 rounded-lg border p-4">
        <FilterBar
          search={
            <SearchInput
              id="integration-search"
              label="Search integrations"
              placeholder="Search integrations"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onClear={() => setQuery("")}
              aria-describedby="integration-filter-note"
            />
          }
          activeFilterCount={activeFilterCount}
          onClearFilters={clearFilters}
        >
          <div className="w-full sm:w-48">
            <Label htmlFor="integration-category" className="sr-only">
              Integration category
            </Label>
            <Select
              id="integration-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              aria-describedby="integration-filter-note"
            >
              <option value="all">All categories</option>
              <option value="crm">CRM</option>
              <option value="communication">Communication</option>
              <option value="calendar">Calendar</option>
              <option value="developer">Automation / developer</option>
            </Select>
          </div>
        </FilterBar>
        <p
          id="integration-filter-note"
          className="text-muted-foreground text-xs"
        >
          These tools need provider setup before they can be connected.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-muted-foreground text-sm" aria-live="polite">
          {resultLabel}
        </p>
        <p className="sr-only" role="status" aria-live="polite">
          {filteredIntegrations.length === 0
            ? "0 integrations match the current filters."
            : `${resultLabel} shown.`}
        </p>
      </div>

      {filteredIntegrations.length > 0 ? (
        <ul
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
          aria-label="Integration catalog"
        >
          {filteredIntegrations.map((integration) => {
            const categoryInfo = categoryPresentation[integration.category];
            const Icon = categoryInfo.icon;
            const descriptionId = `${integration.id}-connection-unavailable`;
            return (
              <li key={integration.id}>
                <Card as="article" variant="subtle" className="h-full">
                  <CardContent className="flex h-full flex-col">
                    <div
                      className="bg-card text-muted-foreground border-border flex size-10 items-center justify-center rounded-lg border"
                      aria-hidden="true"
                    >
                      <Icon className="size-5" />
                    </div>
                    <p className="text-muted-foreground mt-5 text-xs font-medium">
                      {categoryInfo.label}
                    </p>
                    <h3 className="mt-1 text-base font-medium">
                      {integration.name}
                    </h3>
                    <p className="text-muted-foreground mt-1.5 flex-1 text-sm leading-6">
                      {integration.description}
                    </p>
                    <div
                      className="border-border bg-background mt-5 grid gap-1.5 rounded-lg border px-3 py-2.5"
                      title="Not connectable yet"
                      aria-describedby={descriptionId}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <IntegrationStatusBadge status={integration.status} />
                        <span className="text-muted-foreground text-xs">
                          Not connectable yet
                        </span>
                      </div>
                      <span id={descriptionId} className="text-muted-foreground text-xs leading-5">
                        {integration.setupNote ?? DEFAULT_SETUP_NOTE}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          className="max-w-none"
          title="No integrations found"
          description="Try clearing your search or changing the category. The catalog itself is still available."
          action={
            activeFilterCount > 0 ? (
              <Button type="button" variant="outline" onClick={clearFilters}>
                Clear search and filters
              </Button>
            ) : undefined
          }
        />
      )}
    </div>
  );
}
