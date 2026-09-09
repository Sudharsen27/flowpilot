"use client";

import { useEffect, useState } from "react";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import { StatePanel } from "@/components/data-display/state-panel";
import { SectionHeader } from "@/components/layout/section-header";
import { PageHeader } from "@/components/page-header";
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
        description="Review your account, organization, and current workspace membership."
      />
      {isLoading ? (
        <div className="grid gap-6 lg:grid-cols-2" role="status">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
          <span className="sr-only">Loading identity settings</span>
        </div>
      ) : session ? (
        <>
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

          <section className="grid gap-5">
            <SectionHeader
              title="Members"
              description="People who currently belong to this organization."
            />
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

          <section className="grid gap-5">
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
