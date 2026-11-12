import { Suspense } from "react";

import { ResetPasswordPanel } from "@/app/reset-password/reset-password-panel";

function ResetPasswordFallback() {
  return (
    <main className="bg-background flex min-h-svh items-center justify-center px-4 py-10">
      <p className="text-muted-foreground text-sm" role="status">
        Loading password reset…
      </p>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordFallback />}>
      <ResetPasswordPanel />
    </Suspense>
  );
}
