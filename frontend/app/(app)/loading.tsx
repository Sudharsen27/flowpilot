import { Skeleton } from "@/components/ui/skeleton";

export default function AppLoading() {
  return (
    <div className="flex flex-col gap-3" role="status" aria-live="polite">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-4 w-80 max-w-full" />
      <Skeleton className="mt-5 h-36 w-full max-w-2xl" />
      <span className="sr-only">Loading page…</span>
    </div>
  );
}
