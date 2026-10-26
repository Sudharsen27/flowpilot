import Link from "next/link";

import {
  DataTable,
  type DataTableColumn,
} from "@/components/data-display/data-table";
import {
  CompanyProspectStatusBadge,
  EvidenceQualityBadge,
} from "@/components/company-prospects/company-prospect-badges";
import { formatAbsoluteTimestamp } from "@/lib/datetime";
import type { CompanyProspect } from "@/types/api";

const columns: DataTableColumn<CompanyProspect>[] = [
  {
    key: "company",
    header: "Company",
    className: "min-w-[12rem]",
    cell: (prospect) => (
      <div className="min-w-0">
        <Link
          href={`/company-prospects/${prospect.id}`}
          aria-label={prospect.name}
          className="text-foreground decoration-border-strong rounded-sm font-semibold underline underline-offset-4 hover:decoration-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          {prospect.name}
        </Link>
        <p className="text-muted-foreground mt-1 text-xs">
          Name evidence: <EvidenceQualityBadge quality={prospect.name_evidence_quality} />
        </p>
      </div>
    ),
  },
  {
    key: "domain",
    header: "Website domain",
    className: "min-w-[12rem]",
    cell: (prospect) =>
      prospect.website_domain ? (
        <div className="grid gap-1">
          <span className="break-all text-sm">{prospect.website_domain}</span>
          <EvidenceQualityBadge quality={prospect.website_domain_evidence_quality} />
        </div>
      ) : (
        <span className="text-muted-foreground">No domain recorded</span>
      ),
  },
  {
    key: "status",
    header: "Status",
    className: "whitespace-nowrap",
    cell: (prospect) => <CompanyProspectStatusBadge status={prospect.status} />,
  },
  {
    key: "updated",
    header: "Updated",
    className: "whitespace-nowrap",
    cell: (prospect) => formatAbsoluteTimestamp(prospect.updated_at) ?? "Date unavailable",
  },
];

export function CompanyProspectsTable({
  prospects,
  loading,
}: {
  prospects: CompanyProspect[];
  loading: boolean;
}) {
  return (
    <DataTable
      columns={columns}
      rows={prospects}
      getRowKey={(prospect) => prospect.id}
      loading={loading}
      emptyTitle="No company prospects found"
      emptyDescription="Try a different search or lifecycle status."
      headingLevel={3}
    />
  );
}
