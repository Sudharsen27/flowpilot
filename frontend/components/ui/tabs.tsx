"use client";

import { Tabs as TabsPrimitive } from "@base-ui/react/tabs";

import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

function TabsList({ className, ...props }: TabsPrimitive.List.Props) {
  return (
    <TabsPrimitive.List
      data-slot="tabs-list"
      className={cn(
        "border-border relative flex max-w-full gap-1 overflow-x-auto border-b",
        className,
      )}
      {...props}
    />
  );
}

function TabsTrigger({ className, ...props }: TabsPrimitive.Tab.Props) {
  return (
    <TabsPrimitive.Tab
      data-slot="tabs-trigger"
      className={cn(
        "text-muted-foreground hover:text-foreground data-[selected]:text-foreground relative shrink-0 px-3 py-2.5 text-sm font-medium outline-none",
        "focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-inset",
        "after:bg-primary data-[selected]:after:absolute data-[selected]:after:inset-x-2 data-[selected]:after:bottom-0 data-[selected]:after:h-0.5",
        className,
      )}
      {...props}
    />
  );
}

function TabsContent({ className, ...props }: TabsPrimitive.Panel.Props) {
  return (
    <TabsPrimitive.Panel
      data-slot="tabs-content"
      className={cn("py-5 outline-none focus-visible:ring-2", className)}
      {...props}
    />
  );
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
