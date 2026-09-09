import { Building2 } from "lucide-react";

type OrganizationContextProps = {
  organizationName: string;
};

export function OrganizationContext({
  organizationName,
}: OrganizationContextProps) {
  return (
    <div
      data-slot="organization-context"
      className="flex min-w-0 items-center gap-2"
    >
      <span className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
        <Building2 className="size-4" strokeWidth={1.8} aria-hidden="true" />
      </span>
      <span className="min-w-0">
        <span className="text-muted-foreground block text-[0.6875rem] leading-4">
          Current organization
        </span>
        <span className="block max-w-48 truncate text-sm leading-4 font-medium">
          {organizationName}
        </span>
      </span>
    </div>
  );
}
