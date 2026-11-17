"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuthLoading } from "@/components/auth/auth-loading";
import { useAuth } from "@/hooks/use-auth";
import { currentInvitationReturnPath } from "@/lib/invitations/return-path";

export function GuestRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { session, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && session) {
      const returnPath = currentInvitationReturnPath();
      router.replace(
        returnPath ?? (session.emailVerified ? "/dashboard" : "/verify-email/pending"),
      );
    }
  }, [isLoading, router, session]);

  if (isLoading || session) {
    return <AuthLoading />;
  }

  return children;
}
