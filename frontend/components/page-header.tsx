type PageHeaderProps = {
  title: string;
  description: string;
};

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <header className="max-w-2xl">
      <h1 className="text-foreground text-2xl font-semibold tracking-tight">
        {title}
      </h1>
      <p className="text-muted-foreground mt-2 text-sm leading-6">
        {description}
      </p>
    </header>
  );
}
