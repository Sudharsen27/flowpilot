type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="border-border bg-card max-w-lg rounded-lg border px-6 py-8">
      <h2 className="text-foreground text-base font-medium tracking-tight">
        {title}
      </h2>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        {description}
      </p>
    </div>
  );
}
