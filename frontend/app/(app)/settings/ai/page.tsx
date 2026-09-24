import {
  BrainCircuit,
  ChevronRight,
  CircleDollarSign,
  FileSearch,
  Gauge,
  Layers3,
  Network,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";

import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { Select } from "@/components/forms/select";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";

const taskConfigurations = [
  {
    title: "Agent Planning",
    description:
      "Controls how FlowPilot interprets instructions and creates execution plans.",
    icon: Workflow,
  },
  {
    title: "Lead Qualification",
    description: "Controls the model used to analyze and qualify leads.",
    icon: Gauge,
  },
  {
    title: "Response Drafting",
    description:
      "Controls the model used to generate customer response drafts.",
    icon: Sparkles,
  },
  {
    title: "CRM Analysis",
    description:
      "Controls AI analysis of CRM data and customer context.",
    icon: Network,
  },
  {
    title: "Document & Image Analysis",
    description:
      "Controls future AI analysis of documents and visual information.",
    icon: FileSearch,
  },
] as const;

const enterpriseControls = [
  "Organization model policy",
  "Budget limits",
  "Allowed providers",
  "Allowed models",
  "Maximum monthly AI spend",
] as const;

function ProviderCard({
  name,
  description,
  status,
  icon: Icon,
}: {
  name: string;
  description: string;
  status: "draft" | "pending";
  icon: typeof BrainCircuit;
}) {
  return (
    <Card as="article" className="h-full">
      <CardHeader className="flex-row items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="bg-ai/10 text-ai-text flex size-10 shrink-0 items-center justify-center rounded-lg">
            <Icon className="size-5" aria-hidden="true" />
          </div>
          <div className="min-w-0">
            <CardTitle>{name}</CardTitle>
            <CardDescription className="mt-1">{description}</CardDescription>
          </div>
        </div>
        <StatusBadge
          status={status}
          label={status === "pending" ? "Coming soon" : "Not configured"}
          className="shrink-0"
        />
      </CardHeader>
      <CardContent className="pt-4">
        <p className="text-muted-foreground text-xs leading-5">
          Provider connection and credentials will be managed here when AI
          configuration is enabled.
        </p>
      </CardContent>
    </Card>
  );
}

function DisabledConfiguration({
  label,
  value,
  taskTitle,
}: {
  label: string;
  value: string;
  taskTitle: string;
}) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="text-muted-foreground text-xs font-medium">{label}</span>
      <Select aria-label={`${label} for ${taskTitle}`} value={value} disabled>
        <option value={value}>{value}</option>
      </Select>
    </label>
  );
}

export default function AiSettingsPage() {
  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="AI & Automation"
        description="Configure how FlowPilot will use AI across your organization's workflows."
        breadcrumbs={[{ label: "Settings", href: "/settings" }, { label: "AI & Automation" }]}
      />

      <section className="grid gap-5" aria-label="AI Providers">
        <SectionHeader
          title="AI Providers"
          description="Connect the providers your organization is ready to use."
        />
        <div className="grid gap-4 md:grid-cols-2">
          <ProviderCard
            name="Groq"
            description="Fast inference for responsive business workflows."
            status="draft"
            icon={BrainCircuit}
          />
          <ProviderCard
            name="OpenRouter"
            description="A future gateway to a broader model ecosystem."
            status="pending"
            icon={Layers3}
          />
        </div>
      </section>

      <section className="grid gap-5" aria-label="AI Task Configuration">
        <SectionHeader
          title="AI Task Configuration"
          description="Task-specific model selection will be available when multi-model AI configuration is enabled."
        />
        <div className="grid gap-4 lg:grid-cols-2">
          {taskConfigurations.map(({ title, description, icon: Icon }) => (
            <Card as="article" key={title} variant="subtle">
              <CardHeader className="flex-row items-start gap-3">
                <div className="bg-background text-muted-foreground flex size-9 shrink-0 items-center justify-center rounded-md border">
                  <Icon className="size-4" aria-hidden="true" />
                </div>
                <div>
                  <CardTitle>{title}</CardTitle>
                  <CardDescription className="mt-1">{description}</CardDescription>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 sm:grid-cols-2">
                <DisabledConfiguration
                  label="Provider"
                  taskTitle={title}
                  value="Coming soon"
                />
                <DisabledConfiguration
                  label="Model"
                  taskTitle={title}
                  value="Automatic"
                />
                <p className="text-muted-foreground text-xs leading-5 sm:col-span-2">
                  Model selection will be available when multi-model AI configuration is enabled.
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="grid gap-5" aria-label="Model Strategy">
        <SectionHeader
          title="Model Strategy"
          description="A future-ready approach to matching model capabilities with the work at hand."
        />
        <Card variant="information" as="section">
          <CardContent className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Fast models", "Routine classification and lightweight tasks", Gauge],
              ["Reasoning models", "Agent planning and complex decisions", BrainCircuit],
              ["Language models", "Response drafting and communication", Sparkles],
              ["Vision models", "Document and image analysis", FileSearch],
            ].map(([title, description, Icon]) => {
              const StrategyIcon = Icon as typeof BrainCircuit;
              return (
                <div className="flex gap-3" key={title as string}>
                  <StrategyIcon className="text-info-text mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div>
                    <h3 className="text-sm font-medium">{title as string}</h3>
                    <p className="text-muted-foreground mt-1 text-xs leading-5">{description as string}</p>
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card as="section">
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <CircleDollarSign className="text-muted-foreground mt-0.5 size-5" aria-hidden="true" />
              <div>
                <CardTitle>AI Usage & Cost</CardTitle>
                <CardDescription className="mt-1">Current organization-level AI activity.</CardDescription>
              </div>
            </div>
            <StatusBadge status="draft" label="Not available" />
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
              {["Requests this month", "Input tokens", "Output tokens", "Estimated cost"].map((label) => (
                <div key={label}>
                  <dt className="text-muted-foreground text-xs leading-5">{label}</dt>
                  <dd className="mt-1 text-xl font-semibold tracking-tight">—</dd>
                </div>
              ))}
            </dl>
            <p className="text-muted-foreground mt-5 border-t pt-4 text-xs leading-5">
              Usage tracking will become available with AI billing and model telemetry.
            </p>
          </CardContent>
        </Card>

        <Card as="section" variant="information">
          <CardHeader className="flex-row items-start gap-3">
            <ShieldCheck className="text-info-text mt-0.5 size-5" aria-hidden="true" />
            <div>
              <CardTitle>Reliability</CardTitle>
              <CardDescription className="mt-1">Model fallback</CardDescription>
            </div>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-muted-foreground max-w-xl text-sm leading-6">
              FlowPilot will eventually be able to switch providers when a model is unavailable.
            </p>
            <StatusBadge status="pending" label="Coming soon" className="self-start sm:self-auto" />
          </CardContent>
        </Card>
      </div>

      <section className="grid gap-5" aria-label="Enterprise Controls">
        <SectionHeader
          title="Enterprise Controls"
          description="Organization-wide guardrails will be managed here as AI capabilities mature."
        />
        <Card as="section">
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {enterpriseControls.map((label) => (
              <div className="flex items-center justify-between gap-4 rounded-md border bg-surface-subtle px-3 py-3" key={label}>
                <label className="text-sm font-medium" htmlFor={`future-${label}`}>
                  {label}
                </label>
                <div className="flex shrink-0 items-center gap-2">
                  <input
                    id={`future-${label}`}
                    aria-label={`${label}, coming soon`}
                    disabled
                    placeholder="Coming soon"
                    className="w-24 cursor-not-allowed rounded-md border bg-background px-2 py-1.5 text-right text-xs text-foreground-disabled placeholder:text-foreground-disabled"
                  />
                  <ChevronRight className="text-muted-foreground size-4" aria-hidden="true" />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}