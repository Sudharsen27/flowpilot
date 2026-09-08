export function AuthLoading() {
  return (
    <main
      className="flex min-h-full items-center justify-center px-6 py-16"
      aria-live="polite"
      aria-busy="true"
    >
      <p className="text-muted-foreground text-sm">Checking your session…</p>
    </main>
  );
}
