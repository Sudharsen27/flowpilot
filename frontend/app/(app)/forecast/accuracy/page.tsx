"use client";

import { Suspense } from "react";

import { ForecastAccuracyWorkspace } from "@/components/forecast/forecast-accuracy-workspace";
import { Skeleton } from "@/components/ui/skeleton";

function ForecastAccuracyFallback() {
  return (
    <div className="grid gap-4" role="status">
      <Skeleton className="h-12 w-48" />
      <Skeleton className="h-28 w-full" />
      <Skeleton className="h-64 w-full" />
      <span className="sr-only">Loading forecast accuracy</span>
    </div>
  );
}

export default function ForecastAccuracyPage() {
  return (
    <Suspense fallback={<ForecastAccuracyFallback />}>
      <ForecastAccuracyWorkspace />
    </Suspense>
  );
}
