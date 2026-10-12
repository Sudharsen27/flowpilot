import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { AnalyticsDailyPoint } from "@/types/api";

type AnalyticsTrendProps = {
  daily: readonly AnalyticsDailyPoint[];
  loading: boolean;
};

function formatDay(value: string) {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function AnalyticsTrend({ daily, loading }: AnalyticsTrendProps) {
  const peak = Math.max(1, ...daily.map((point) => point.leads_created));
  const hasData = daily.some(
    (point) => point.leads_created || point.ai_analyses || point.emails_sent,
  );

  return (
    <Card
      as="section"
      aria-labelledby="analytics-trend-title"
      aria-busy={loading || undefined}
    >
      <CardContent className="grid gap-4">
        <div>
          <h3
            id="analytics-trend-title"
            className="text-base font-medium tracking-tight"
          >
            Daily leads
          </h3>
          <p className="text-muted-foreground mt-1 text-sm leading-6">
            New leads per day. The table below lists each day with AI analyses
            and emails sent.
          </p>
        </div>
        {loading ? (
          <div role="status">
            <Skeleton className="h-32 w-full" />
            <span className="sr-only">Loading daily leads</span>
          </div>
        ) : !hasData ? (
          <p className="text-muted-foreground border-border rounded-md border border-dashed px-3 py-6 text-center text-sm">
            No leads, analyses, or emails in this period yet.
          </p>
        ) : (
          <>
            <div className="flex h-32 items-end gap-px" aria-hidden="true">
              {daily.map((point) => (
                <div
                  key={point.date}
                  title={`${formatDay(point.date)}: ${point.leads_created} leads`}
                  className="bg-primary/80 min-h-px flex-1 rounded-t-sm"
                  style={{ height: `${(point.leads_created / peak) * 100}%` }}
                />
              ))}
            </div>
            <details className="text-sm">
              <summary className="text-muted-foreground cursor-pointer text-xs">
                Show daily numbers
              </summary>
              <table className="mt-2 w-full text-left text-xs">
                <thead className="text-muted-foreground">
                  <tr>
                    <th scope="col" className="py-1 font-medium">
                      Day
                    </th>
                    <th scope="col" className="py-1 text-right font-medium">
                      Leads
                    </th>
                    <th scope="col" className="py-1 text-right font-medium">
                      AI analyses
                    </th>
                    <th scope="col" className="py-1 text-right font-medium">
                      Emails sent
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {daily.map((point) => (
                    <tr key={point.date} className="border-border border-t">
                      <th scope="row" className="py-1 font-normal">
                        {formatDay(point.date)}
                      </th>
                      <td className="py-1 text-right tabular-nums">
                        {point.leads_created}
                      </td>
                      <td className="py-1 text-right tabular-nums">
                        {point.ai_analyses}
                      </td>
                      <td className="py-1 text-right tabular-nums">
                        {point.emails_sent}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </CardContent>
    </Card>
  );
}
