"use client";

import { Suspense } from "react";

import { ForecastWorkspace } from "@/components/forecast/forecast-workspace";
import { Skeleton } from "@/components/ui/skeleton";

function ForecastFallback() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-12 w-48" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading forecast</span>
    </div>
  );
}

export default function ForecastPage() {
  return (
    <Suspense fallback={<ForecastFallback />}>
      <ForecastWorkspace />
    </Suspense>
  );
}
