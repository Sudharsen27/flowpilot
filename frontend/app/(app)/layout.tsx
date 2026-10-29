import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { ProtectedRoute } from "@/components/auth/protected-route";
import { QueryProvider } from "@/components/providers/query-provider";
import { AuthProvider } from "@/hooks/use-auth";

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <QueryProvider>
        <ProtectedRoute>
          <AppShell>{children}</AppShell>
        </ProtectedRoute>
      </QueryProvider>
    </AuthProvider>
  );
}
