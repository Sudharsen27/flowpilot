"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, BrainCircuit } from "lucide-react";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
import { WebsiteEnquirySettings } from "@/components/settings/website-enquiry-settings";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import { apiGet } from "@/lib/api/client";
import type { MemberPublic, MembershipRole } from "@/types/api";

const roleLabels: Record<MembershipRole, string> = {
  OWNER: "Owner",
  ADMIN: "Admin",
  MEMBER: "Member",
};

const memberColumns: DataTableColumn<MemberPublic>[] = [
  {
    key: "name",
    header: "Name",
    cell: (member) => <span className="font-medium">{member.user.name}</span>,
  },
  {
    key: "email",
    header: "Email",
    cell: (member) => (
      <span className="text-muted-foreground">{member.user.email}</span>
    ),
  },
  {
    key: "role",
    header: "Role",
    cell: (member) => roleLabels[member.role],
  },
];

export default function SettingsPage() {
  const { session, isLoading, signOut } = useAuth();
  const [members, setMembers] = useState<MemberPublic[] | null>(null);
  const [membersError, setMembersError] = useState(false);
  const [requestVersion, setRequestVersion] = useState(0);

  useEffect(() => {
    if (!session) {
      return;
    }

    let cancelled = false;
    void apiGet<MemberPublic[]>("/api/v1/organizations/current/members")
      .then((response) => {
        if (!cancelled) {
          setMembers(response);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setMembersError(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [requestVersion, session]);

  function retryMembers() {
    setMembers(null);
    setMembersError(false);
    setRequestVersion((version) => version + 1);
  }

  return (
    <div className="gap-section flex flex-col">
      <PageHeader
        title="Settings"
        description="Manage General, Team, Automation, and Account settings for your current workspace."
      />
      {isLoading ? (
        <div className="grid gap-6 lg:grid-cols-2" role="status">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
          <span className="sr-only">Loading identity settings</span>
        </div>
      ) : session ? (
        <>
          <section className="grid gap-5" aria-label="General settings">
            <SectionHeader
              title="General"
              description="Identity and organization details for your current workspace."
            />
            <div className="grid gap-6 lg:grid-cols-2">
              <Card as="section">
                <CardHeader>
                  <CardTitle>User profile</CardTitle>
                  <CardDescription>
                    Identity associated with your current session.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Full name
                      </dt>
                      <dd className="mt-1 text-sm font-medium">
                        {session.user.name}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Email
                      </dt>
                      <dd className="mt-1 text-sm break-all">
                        {session.user.email}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Membership role
                      </dt>
                      <dd className="mt-1 text-sm">
                        {roleLabels[session.membership.role]}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Organization
                      </dt>
                      <dd className="mt-1 text-sm">
                        {session.organization.name}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>

              <Card as="section">
                <CardHeader>
                  <CardTitle>Organization</CardTitle>
                  <CardDescription>
                    Current workspace context for this session.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-5">
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Organization name
                      </dt>
                      <dd className="mt-1 text-sm font-medium">
                        {session.organization.name}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Organization slug
                      </dt>
                      <dd className="mt-1 font-mono text-sm">
                        {session.organization.slug}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground text-xs font-medium">
                        Your role
                      </dt>
                      <dd className="mt-1 text-sm">
                        {roleLabels[session.membership.role]}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="grid gap-5" aria-label="Team settings">
            <SectionHeader title="Team" description="People who currently belong to this organization." />
            {membersError ? (
              <StatePanel
                kind="error"
                title="Members could not be loaded"
                description="Try again to retrieve the current organization members."
                action={<Button onClick={retryMembers}>Try again</Button>}
              />
            ) : (
              <DataTable
                columns={memberColumns}
                rows={members ?? []}
                getRowKey={(member) => member.membership_id}
                loading={members === null}
                emptyTitle="No organization members"
                emptyDescription="No members were returned for the current organization."
              />
            )}
          </section>

          <section className="grid gap-5" aria-label="Automation settings">
            <SectionHeader
              title="Automation"
              description="Configure the automated experiences that work across your organization."
            />
            <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
              <div className="grid gap-5">
                <SectionHeader
                  title="Website enquiries"
                  description="Hosted form for website visitors. Email is not sent until a person approves a response."
                />
                <WebsiteEnquirySettings
                  slug={session.organization.slug}
                  role={session.membership.role}
                />
              </div>
              <Link
                href="/settings/ai"
                aria-label="AI & Automation settings"
                className="group block rounded-lg outline-none focus-visible:ring-ring focus-visible:ring-2"
              >
                <Card
                  as="article"
                  variant="interactive"
                  className="h-full transition-shadow group-hover:shadow-md"
                >
                  <CardHeader className="flex-row items-start justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <div className="bg-ai/10 text-ai-text flex size-10 shrink-0 items-center justify-center rounded-lg">
                        <BrainCircuit className="size-5" aria-hidden="true" />
                      </div>
                      <div>
                        <CardTitle>AI &amp; Automation</CardTitle>
                        <CardDescription className="mt-1">
                          Configure how FlowPilot uses AI across your organization&apos;s workflows.
                        </CardDescription>
                      </div>
                    </div>
                    <ArrowRight
                      className="text-muted-foreground mt-1 size-4 shrink-0 transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </CardHeader>
                  <CardContent className="pt-4">
                    <p className="text-muted-foreground text-xs leading-5">
                      Open AI providers, task configuration, model strategy, and future enterprise controls.
                    </p>
                    <span className="text-primary mt-4 inline-flex items-center text-sm font-medium">
                      Open AI settings
                      <ArrowRight className="ml-1.5 size-4" aria-hidden="true" />
                    </span>
                  </CardContent>
                </Card>
              </Link>
            </div>
          </section>

          <section className="grid gap-5" aria-label="Account settings">
            <SectionHeader
              title="Account"
              description="Manage this browser session."
            />
            <Card className="max-w-2xl">
              <CardHeader>
                <CardTitle>Sign out</CardTitle>
                <CardDescription>
                  End your FlowPilot session on this browser.
                </CardDescription>
              </CardHeader>
              <CardFooter>
                <Button variant="outline" onClick={signOut}>
                  Sign out
                </Button>
              </CardFooter>
            </Card>
          </section>
        </>
      ) : (
        <StatePanel
          kind="unavailable"
          title="Session unavailable"
          description="Sign in again to review your identity and organization settings."
        />
      )}
    </div>
  );
}
