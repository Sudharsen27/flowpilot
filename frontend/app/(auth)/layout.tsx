import type { ReactNode } from "react";

import { GuestRoute } from "@/components/auth/guest-route";
import { AuthProvider } from "@/hooks/use-auth";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <GuestRoute>{children}</GuestRoute>
    </AuthProvider>
  );
}
