import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

describe("interaction primitives", () => {
  it("opens a dialog, closes with Escape, and restores trigger focus", async () => {
    const user = userEvent.setup();
    render(
      <Dialog>
        <DialogTrigger>Open details</DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Details</DialogTitle>
            <DialogDescription>Review the available details.</DialogDescription>
          </DialogHeader>
          <button type="button">Continue</button>
        </DialogContent>
      </Dialog>,
    );

    const trigger = screen.getByRole("button", { name: "Open details" });
    await user.click(trigger);

    expect(screen.getByRole("dialog", { name: "Details" })).toBeVisible();
    await user.keyboard("{Escape}");
    await waitFor(() =>
      expect(
        screen.queryByRole("dialog", { name: "Details" }),
      ).not.toBeInTheDocument(),
    );
    expect(trigger).toHaveFocus();
  });

  it("supports keyboard selection in a dropdown menu", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(
      <DropdownMenu>
        <DropdownMenuTrigger>Open actions</DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onClick={onSelect}>Archive</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    const trigger = screen.getByRole("button", { name: "Open actions" });
    trigger.focus();
    await user.keyboard("{Enter}");

    const item = await screen.findByRole("menuitem", { name: "Archive" });
    expect(item).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("moves focus and selection between tabs with arrow keys", async () => {
    const user = userEvent.setup();
    render(
      <Tabs defaultValue="overview">
        <TabsList aria-label="Agent details">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
        </TabsList>
        <TabsContent value="overview">Overview content</TabsContent>
        <TabsContent value="activity">Activity content</TabsContent>
      </Tabs>,
    );

    const overview = screen.getByRole("tab", { name: "Overview" });
    const activity = screen.getByRole("tab", { name: "Activity" });

    overview.focus();
    expect(overview).toHaveFocus();
    expect(overview).toHaveAttribute("aria-selected", "true");

    await user.keyboard("{ArrowRight}");
    expect(activity).toHaveFocus();
    expect(activity).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Overview content");

    await user.keyboard("{Enter}");
    expect(activity).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Activity content");

    await user.keyboard("{ArrowLeft}");
    expect(overview).toHaveFocus();
    expect(overview).toHaveAttribute("aria-selected", "false");

    await user.keyboard(" ");
    expect(overview).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Overview content");
  });
});
