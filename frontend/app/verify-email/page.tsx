import { Suspense } from "react";

import { VerifyEmailPanel } from "@/app/verify-email/verify-email-panel";

function VerifyEmailFallback() {
  return (
    <main className="bg-background flex min-h-svh items-center justify-center px-4 py-10">
      <p className="text-muted-foreground text-sm" role="status">
        Verifying your email…
      </p>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<VerifyEmailFallback />}>
      <VerifyEmailPanel />
    </Suspense>
  );
}
