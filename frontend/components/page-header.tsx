import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

type PageHeaderProps = {
  title: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  primaryAction?: ReactNode;
  secondaryActions?: ReactNode;
  className?: string;
};

export function PageHeader({
  title,
  description,
  breadcrumbs,
  primaryAction,
  secondaryActions,
  className,
}: PageHeaderProps) {
  return (
    <header
      data-slot="page-header"
      className={cn(
        "flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between",
        className,
      )}
    >
      <div className="max-w-3xl min-w-0">
        {breadcrumbs?.length ? (
          <nav aria-label="Breadcrumb" className="mb-2">
            <ol className="text-muted-foreground flex flex-wrap items-center gap-1.5 text-xs">
              {breadcrumbs.map((item, index) => (
                <li
                  key={`${item.label}-${index}`}
                  className="flex items-center gap-1.5"
                >
                  {index > 0 ? <span aria-hidden="true">/</span> : null}
                  {item.href && index < breadcrumbs.length - 1 ? (
                    <a
                      href={item.href}
                      className="hover:text-foreground rounded-sm underline-offset-4 hover:underline"
                    >
                      {item.label}
                    </a>
                  ) : (
                    <span
                      aria-current={
                        index === breadcrumbs.length - 1 ? "page" : undefined
                      }
                    >
                      {item.label}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        ) : null}
        <h1 className="text-foreground text-page-title font-semibold tracking-tight">
          {title}
        </h1>
        {description ? (
          <p className="text-muted-foreground mt-2 max-w-2xl text-sm leading-6">
            {description}
          </p>
        ) : null}
      </div>
      {primaryAction || secondaryActions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
          {secondaryActions}
          {primaryAction}
        </div>
      ) : null}
    </header>
  );
}
