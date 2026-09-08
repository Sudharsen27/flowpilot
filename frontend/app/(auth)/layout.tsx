import type { ReactNode } from "react";

import { GuestRoute } from "@/components/auth/guest-route";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return <GuestRoute>{children}</GuestRoute>;
}
