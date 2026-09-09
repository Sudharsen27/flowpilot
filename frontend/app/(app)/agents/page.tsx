"use client";

import { Plus, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { AgentBlueprints } from "@/components/agents/agent-blueprints";
import { AgentGrid } from "@/components/agents/agent-grid";
import { AgentOverview } from "@/components/agents/agent-overview";
import { StatePanel } from "@/components/data-display/state-panel";
import { Input } from "@/components/forms/input";
import { Select } from "@/components/forms/select";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgents } from "@/lib/api/agents";
import type { Agent, AgentStatus, AgentType } from "@/types/api";

const statusToCard = {
  DRAFT: "draft",
  READY: "ready",
  ACTIVE: "active",
  PAUSED: "paused",
  NEEDS_ATTENTION: "needs-attention",
} as const;

function readableType(type: AgentType) {
  return type.charAt(0) + type.slice(1).toLowerCase();
}

function readableDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(date);
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [status, setStatus] = useState<AgentStatus | "">("");
  const [agentType, setAgentType] = useState<AgentType | "">("");
  const [search, setSearch] = useState("");
  const [retryKey, setRetryKey] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void getAgents({
      status: status || undefined,
      agentType: agentType || undefined,
    })
      .then((data) => {
        if (!cancelled) {
          setAgents(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasError(true);
          setAgents([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [agentType, retryKey, status]);

  const visibleAgents = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return agents;
    return agents.filter(
      (agent) =>
        agent.name.toLowerCase().includes(query) ||
        agent.description.toLowerCase().includes(query),
    );
  }, [agents, search]);

  const cards = visibleAgents.map((agent) => ({
    id: agent.id,
    name: agent.name,
    description: agent.description,
    agentType: readableType(agent.agent_type),
    status: statusToCard[agent.status],
    configurationState:
      agent.status === "DRAFT" ? "Draft configuration" : "Configured",
    updatedAt: readableDate(agent.updated_at),
  }));

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI Agents"
        description="Configure AI workers that can help execute clearly defined business tasks within controlled boundaries."
        primaryAction={
          <>
            <Button
              type="button"
              disabled
              aria-describedby="create-agent-unavailable"
            >
              <Plus aria-hidden="true" />
              Create agent
            </Button>
            <span id="create-agent-unavailable" className="sr-only">
              Agent creation is not available yet.
            </span>
          </>
        }
      />

      <section className="grid gap-5">
        <SectionHeader
          title="Agent overview"
          description="Configuration counts derived from the currently loaded agent list. Runtime performance is not included."
        />
        <AgentOverview
          total={agents.length}
          active={agents.filter((agent) => agent.status === "ACTIVE").length}
          needsAttention={
            agents.filter((agent) => agent.status === "NEEDS_ATTENTION").length
          }
          draft={agents.filter((agent) => agent.status === "DRAFT").length}
          loading={isLoading}
        />
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Configured agents"
          description="Manage each agent's purpose, capabilities, configuration, and operating status."
        />
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem_12rem]">
          <label className="relative">
            <span className="sr-only">Search loaded agents</span>
            <Search
              className="text-muted-foreground pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2"
              aria-hidden="true"
            />
            <Input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="pl-9"
              placeholder="Search loaded agents"
            />
          </label>
          <Select
            aria-label="Agent status"
            value={status}
            onChange={(event) => {
              setIsLoading(true);
              setHasError(false);
              setStatus(event.target.value as AgentStatus | "");
            }}
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="READY">Ready</option>
            <option value="ACTIVE">Active</option>
            <option value="PAUSED">Paused</option>
            <option value="NEEDS_ATTENTION">Needs attention</option>
          </Select>
          <Select
            aria-label="Agent type"
            value={agentType}
            onChange={(event) => {
              setIsLoading(true);
              setHasError(false);
              setAgentType(event.target.value as AgentType | "");
            }}
          >
            <option value="">All types</option>
            <option value="SALES">Sales</option>
            <option value="SUPPORT">Support</option>
            <option value="OPERATIONS">Operations</option>
            <option value="COMMUNICATION">Communication</option>
          </Select>
        </div>
        {isLoading ? (
          <div
            className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
            role="status"
          >
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
            <Skeleton className="h-64" />
            <span className="sr-only">Loading agents</span>
          </div>
        ) : hasError ? (
          <StatePanel
            kind="error"
            className="max-w-none"
            title="Agents could not be loaded"
            description="Check your connection and try again."
            action={
              <Button
                type="button"
                onClick={() => {
                  setIsLoading(true);
                  setHasError(false);
                  setRetryKey((key) => key + 1);
                }}
              >
                Retry
              </Button>
            }
          />
        ) : search && cards.length === 0 ? (
          <StatePanel
            className="max-w-none"
            title="No loaded agents match"
            description="Search is applied locally to the agents returned by the selected server filters."
            action={
              <Button type="button" variant="outline" onClick={() => setSearch("")}>
                Clear search
              </Button>
            }
          />
        ) : (
          <AgentGrid agents={cards} />
        )}
      </section>

      <section className="grid gap-5">
        <SectionHeader
          title="Agent blueprints"
          description="Planned role and capability concepts for future configuration. These are not active agents."
        />
        <AgentBlueprints />
      </section>
    </div>
  );
}
