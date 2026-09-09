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
}: UserMenuProps) {
  const router = useRouter();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            aria-label={`Open user menu for ${user.name}`}
            className="h-9 gap-2 px-1.5 sm:px-2"
          />
        }
      >
        <span className="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-md text-[0.6875rem] font-semibold">
          {getInitials(user.name)}
        </span>
        <span className="hidden max-w-32 truncate text-sm font-medium md:block">
          {user.name}
        </span>
        <ChevronDown
          className="text-muted-foreground hidden size-3.5 sm:block"
          aria-hidden="true"
        />
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
