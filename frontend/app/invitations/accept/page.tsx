import { Suspense } from "react";

import { InvitationAcceptPanel } from "@/app/invitations/accept/invitation-accept-panel";

function InvitationAcceptFallback() {
  return (
    <main className="bg-background flex min-h-svh items-center justify-center px-4 py-10">
      <p className="text-muted-foreground text-sm" role="status">
        Checking this invitation…
      </p>
    </main>
  );
}

export default function InvitationAcceptPage() {
  return (
    <Suspense fallback={<InvitationAcceptFallback />}>
      <InvitationAcceptPanel />
    </Suspense>
  );
}
