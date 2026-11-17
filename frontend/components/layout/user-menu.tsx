"use client";

import { ChevronDown, LogOut, Settings } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { apiErrorDetail } from "@/lib/api/error-detail";
import { listMyOrganizations } from "@/lib/api/invitations";
import type { MembershipRole, UserOrganizationPublic, UserPublic } from "@/types/api";

type UserMenuProps = {
  user: UserPublic;
  organizationName: string;
  organizationId: string;
  role: MembershipRole;
  onSignOut: () => void;
  onSwitchOrganization?: (organizationId: string) => Promise<void> | void;
  /** "sidebar": full-width account row for the bottom of the sidebar. */
  variant?: "compact" | "sidebar";
  /** Sidebar only: show just the avatar. */
  collapsed?: boolean;
};

const roleLabels: Record<MembershipRole, string> = {
  OWNER: "Owner",
  ADMIN: "Admin",
  MEMBER: "Member",
};

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "?";
  }
  return parts
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function UserMenu({
  user,
  organizationName,
  organizationId,
  role,
  onSignOut,
  onSwitchOrganization,
  variant = "compact",
  collapsed = false,
}: UserMenuProps) {
  const router = useRouter();
  const [organizations, setOrganizations] = useState<UserOrganizationPublic[] | null>(null);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [switchError, setSwitchError] = useState<string | null>(null);
  const sidebar = variant === "sidebar";
  const avatar = (
    <span className="bg-brand-subtle text-brand-text ring-brand-border flex size-7 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-semibold ring-1">
      {getInitials(user.name)}
    </span>
  );

  return (
    <div className={sidebar ? "w-full" : undefined}>
    <DropdownMenu
      onOpenChange={(open) => {
        if (!open || organizations !== null) {
          return;
        }
        void listMyOrganizations()
          .then(setOrganizations)
          .catch(() => setOrganizations([]));
      }}
    >
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            aria-label={`Open user menu for ${user.name}`}
            className={
              sidebar
                ? collapsed
                  ? "size-9 p-0"
                  : "h-auto w-full justify-start gap-2.5 px-2 py-1.5 text-left"
                : "h-9 gap-2 px-1.5 sm:px-2"
            }
          />
        }
      >
        {avatar}
        {sidebar ? (
          collapsed ? null : (
            <>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[0.8125rem] leading-4 font-medium">
                  {user.name}
                </span>
                <span className="text-muted-foreground block text-[0.6875rem] leading-4">
                  {roleLabels[role]}
                </span>
              </span>
              <ChevronDown
                className="text-muted-foreground size-3.5"
                aria-hidden="true"
              />
            </>
          )
        ) : (
          <>
            <span className="hidden max-w-32 truncate text-sm font-medium md:block">
              {user.name}
            </span>
            <ChevronDown
              className="text-muted-foreground hidden size-3.5 sm:block"
              aria-hidden="true"
            />
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64">
        <div className="px-2 py-2">
          <p className="truncate text-sm font-medium">{user.name}</p>
          <p className="text-muted-foreground mt-0.5 truncate text-xs">
            {user.email}
          </p>
          <p className="text-muted-foreground mt-1 truncate text-xs">
            {organizationName}
          </p>
          <p className="text-muted-foreground mt-1 text-xs">
            Role: {roleLabels[role]}
          </p>
        </div>
        <DropdownMenuSeparator />
        {organizations && organizations.length > 0 ? (
          <>
            <p className="text-muted-foreground px-2 py-1 text-xs">Organizations</p>
            {organizations.map((organization) => {
              const current = organization.organization_id === organizationId;
              return (
                <DropdownMenuItem
                  key={organization.organization_id}
                  disabled={current || switchingId !== null || !onSwitchOrganization}
                  onClick={() => {
                    if (!onSwitchOrganization || current) {
                      return;
                    }
                    setSwitchError(null);
                    setSwitchingId(organization.organization_id);
                    void Promise.resolve(onSwitchOrganization(organization.organization_id))
                      .then(() => undefined)
                      .catch((cause: unknown) => {
                        setSwitchError(
                          apiErrorDetail(
                            cause,
                            "The organization could not be switched. Try again.",
                          ),
                        );
                      })
                      .finally(() => setSwitchingId(null));
                  }}
                >
                  {switchingId === organization.organization_id
                    ? "Switching…"
                    : current
                      ? `${organization.name} (current)`
                      : organization.name}
                </DropdownMenuItem>
              );
            })}
            <DropdownMenuSeparator />
          </>
        ) : null}
        <DropdownMenuItem onClick={() => router.push("/settings")}>
          <Settings aria-hidden="true" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuItem onClick={onSignOut}>
          <LogOut aria-hidden="true" />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
    {switchError ? (
      <p className="text-danger-text px-2 py-1 text-xs" role="alert">
        {switchError}
      </p>
    ) : null}
  </div>
  );
}
