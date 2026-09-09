import { ExecutionStatusBadge, formatTimestamp } from "@/components/agents/execution-status";
import { cn } from "@/lib/utils";
import type { AgentExecutionListItem } from "@/types/api";

type AgentExecutionHistoryItemProps = {
  item: AgentExecutionListItem;
  selected: boolean;
  onSelect: (id: string) => void;
};

export function AgentExecutionHistoryItem({
  item,
  selected,
  onSelect,
}: AgentExecutionHistoryItemProps) {
  const created = formatTimestamp(item.created_at);
  return (
    <li>
      <button
        type="button"
        id={`execution-history-${item.id}`}
        aria-pressed={selected}
        aria-current={selected ? "true" : undefined}
        aria-label={`View execution ${item.id}`}
        onClick={() => onSelect(item.id)}
        className={cn(
          "border-border hover:bg-muted/60 focus-visible:ring-ring w-full rounded-md border px-3 py-3 text-left outline-none focus-visible:ring-2",
          selected ? "border-ring bg-muted/40" : "bg-background",
        )}
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <ExecutionStatusBadge status={item.status} />
          {created ? (
            <time
              className="text-muted-foreground text-xs"
              dateTime={item.created_at}
            >
              {created}
            </time>
          ) : null}
        </div>
        <p className="mt-2 font-mono text-xs break-all">{item.id}</p>
        {item.input_preview ? (
          <p className="mt-2 text-sm leading-5">{item.input_preview}</p>
        ) : null}
        {item.error_preview ? (
          <p className="text-danger-text mt-1 text-xs leading-5">
            {item.error_preview}
          </p>
        ) : null}
        <dl className="text-muted-foreground mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {item.provider ? (
            <div>
              <dt className="sr-only">Provider</dt>
              <dd>{item.provider}</dd>
            </div>
          ) : null}
          {item.model ? (
            <div>
              <dt className="sr-only">Model</dt>
              <dd>{item.model}</dd>
            </div>
          ) : null}
          {item.started_at ? (
            <div>
              <dt className="inline">Started </dt>
              <dd className="inline">{formatTimestamp(item.started_at)}</dd>
            </div>
          ) : null}
          {item.completed_at ? (
            <div>
              <dt className="inline">Completed </dt>
              <dd className="inline">{formatTimestamp(item.completed_at)}</dd>
            </div>
          ) : null}
        </dl>
      </button>
    </li>
  );
}
