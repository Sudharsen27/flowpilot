"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { AuthLoading } from "@/components/auth/auth-loading";
import { useAuth } from "@/hooks/use-auth";

export function GuestRoute({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { session, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && session) {
      router.replace("/");
    }
  }, [isLoading, router, session]);

  if (isLoading || session) {
    return <AuthLoading />;
  }

  return children;
}
