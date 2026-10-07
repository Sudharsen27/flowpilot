"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  NAV_GROUPS,
  SECONDARY_NAV_ITEMS,
  SETTINGS_ITEM,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";

const destinations = [
  ...NAV_GROUPS.flatMap((group) =>
    group.items.map((item) => ({ ...item, group: group.label })),
  ),
  ...SECONDARY_NAV_ITEMS.map((item) => ({
    ...item,
    group: item.status === "available" ? "Records" : "Planned",
  })),
  { ...SETTINGS_ITEM, group: "Workspace" },
];

export function CommandLauncher() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((current) => !current);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return destinations;
    return destinations.filter((item) =>
      `${item.label} ${item.group}`.toLowerCase().includes(needle),
    );
  }, [query]);

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        aria-label="Open command menu"
        className="text-muted-foreground h-8 w-9 justify-start px-2 sm:w-56"
        onClick={() => setOpen(true)}
      >
        <Search aria-hidden="true" />
        <span className="hidden flex-1 truncate text-left sm:inline">Go to a workspace</span>
        <kbd className="border-border text-muted-foreground hidden rounded border px-1.5 py-0.5 font-mono text-[0.625rem] sm:inline">
          ⌘K
        </kbd>
      </Button>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) setQuery("");
        }}
      >
        <DialogContent className="gap-0 overflow-hidden p-0 sm:max-w-md">
          <DialogHeader className="sr-only">
            <DialogTitle>Command menu</DialogTitle>
            <DialogDescription>
              Jump to a FlowPilot workspace. This menu does not search lead or conversation records.
            </DialogDescription>
          </DialogHeader>
          <label className="border-border flex items-center gap-2 border-b px-3">
            <Search className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
            <span className="sr-only">Filter workspaces</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Filter workspaces"
              className="h-11 w-full bg-transparent text-sm outline-none"
              autoFocus
            />
          </label>
          <ul className="max-h-80 overflow-y-auto p-2" aria-label="Workspaces">
            {matches.length === 0 ? (
              <li className="text-muted-foreground px-3 py-6 text-center text-sm">
                No matching workspace.
              </li>
            ) : (
              matches.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.href}>
                    <button
                      type="button"
                      onClick={() => go(item.href)}
                      className={cn(
                        "hover:bg-muted focus-visible:ring-ring flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm outline-none focus-visible:ring-2",
                      )}
                    >
                      <Icon className="text-muted-foreground size-4 shrink-0" aria-hidden="true" />
                      <span className="min-w-0 flex-1 truncate font-medium">{item.label}</span>
                      <span className="text-muted-foreground text-xs">{item.group}</span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        </DialogContent>
      </Dialog>
    </>
  );
}
