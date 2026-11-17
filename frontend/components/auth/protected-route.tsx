"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuthLoading } from "@/components/auth/auth-loading";
import { useAuth } from "@/hooks/use-auth";

const PENDING_VERIFICATION_PATH = "/verify-email/pending";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { session, isLoading } = useAuth();
  const verified = session?.emailVerified === true;
  const onPendingPage = pathname === PENDING_VERIFICATION_PATH;

  useEffect(() => {
    if (isLoading) {
      return;
    }
    if (!session) {
      router.replace("/login");
      return;
    }
    if (!verified && !onPendingPage) {
      router.replace(PENDING_VERIFICATION_PATH);
      return;
    }
    if (verified && onPendingPage) {
      router.replace("/dashboard");
    }
  }, [isLoading, onPendingPage, router, session, verified]);

  if (isLoading || !session || (!verified && !onPendingPage) || (verified && onPendingPage)) {
    return <AuthLoading />;
  }

  return children;
}
