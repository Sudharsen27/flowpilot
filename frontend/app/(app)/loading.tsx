export default function AppLoading() {
  return (
    <div className="flex flex-col gap-3" aria-live="polite" aria-busy="true">
      <div className="bg-muted h-7 w-48 animate-pulse rounded" />
      <div className="bg-muted h-4 w-80 max-w-full animate-pulse rounded" />
      <span className="sr-only">Loading page…</span>
    </div>
  );
}
