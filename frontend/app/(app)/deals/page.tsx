"use client";

import { Suspense } from "react";

import { DealsWorkspace } from "@/components/deals/deals-workspace";
import { Skeleton } from "@/components/ui/skeleton";

function DealsFallback() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-12 w-48" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading deals</span>
    </div>
  );
}

export default function DealsPage() {
  return (
    <Suspense fallback={<DealsFallback />}>
      <DealsWorkspace />
    </Suspense>
  );
}
