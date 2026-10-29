"use client";

import { ChevronDown, LogOut, Settings } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { MembershipRole, UserPublic } from "@/types/api";

type UserMenuProps = {
  user: UserPublic;
  organizationName: string;
  role: MembershipRole;
  onSignOut: () => void;
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
  role,
  onSignOut,
  variant = "compact",
  collapsed = false,
}: UserMenuProps) {
  const router = useRouter();
  const sidebar = variant === "sidebar";
  const avatar = (
    <span className="bg-brand-subtle text-brand-text ring-brand-border flex size-7 shrink-0 items-center justify-center rounded-full text-[0.6875rem] font-semibold ring-1">
      {getInitials(user.name)}
    </span>
  );

  return (
    <DropdownMenu>
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
  );
}
