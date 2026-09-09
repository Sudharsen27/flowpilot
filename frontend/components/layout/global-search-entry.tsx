"use client";

import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

export function GlobalSearchEntry() {
  return (
    <Dialog>
      <DialogTrigger
        render={
          <Button
            variant="outline"
            aria-label="Open global search"
            className="text-muted-foreground w-9 justify-start px-2.5 sm:w-52"
          />
        }
      >
        <Search aria-hidden="true" />
        <span className="hidden sm:inline">Search FlowPilot</span>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Global search</DialogTitle>
          <DialogDescription>
            Search across your FlowPilot workspace is not available yet. It will
            be connected when product search is implemented.
          </DialogDescription>
        </DialogHeader>
      </DialogContent>
    </Dialog>
  );
}
