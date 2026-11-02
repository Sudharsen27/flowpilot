import { render, screen } from "@testing-library/react";
import { cn } from "cn";
import { describe, expect, it } from "vitest";

import { Button, buttonVariants } from "@/components/ui/button";

const VARIANTS = ["default", "outline", "secondary", "ghost", "destructive", "link"] as const;
const SIZES = ["default", "xs", "sm", "lg", "icon", "icon-xs", "icon-sm", "icon-lg"] as const;
const NON_OUTLINE_VARIANTS = VARIANTS.filter((variant) => variant !== "outline");
const ICON_SIZE_4 = "[&_svg:not([class*='size-'])]:size-4";

function classes(value: string) {
  return value.split(/\s+/).filter(Boolean);
}

describe("buttonVariants", () => {
  it.each(VARIANTS.flatMap((variant) => SIZES.map((size) => [variant, size] as const)))(
    "returns already-merged classes for variant %s and size %s",
    (variant, size) => {
      const value = buttonVariants({ variant, size });
      expect(cn(value)).toBe(value);
      expect(new Set(classes(value)).size).toBe(classes(value).length);
    },
  );

  it("keeps a visible outline border in light theme and the input border in dark theme", () => {
    const outline = classes(buttonVariants({ variant: "outline" }));
    expect(outline).toContain("border");
    expect(outline).toContain("border-border");
    expect(outline).toContain("dark:border-input");
    expect(outline).not.toContain("border-transparent");
  });

  it.each(NON_OUTLINE_VARIANTS)("keeps the transparent border on the %s variant", (variant) => {
    const value = classes(buttonVariants({ variant }));
    expect(value).toContain("border");
    expect(value).toContain("border-transparent");
    expect(value).not.toContain("border-border");
  });

  it("uses the default variant and size when called without arguments", () => {
    expect(buttonVariants()).toBe(buttonVariants({ variant: "default", size: "default" }));
    expect(classes(buttonVariants())).toContain("bg-primary");
    expect(classes(buttonVariants())).toContain("h-8");
  });

  it.each([
    ["sm", "rounded-[min(var(--radius-md),12px)]", "[&_svg:not([class*='size-'])]:size-3.5"],
    ["xs", "rounded-[min(var(--radius-md),10px)]", "[&_svg:not([class*='size-'])]:size-3"],
    ["icon-xs", "rounded-[min(var(--radius-md),10px)]", "[&_svg:not([class*='size-'])]:size-3"],
  ] as const)("uses the %s radius and icon size instead of the base ones", (size, radius, iconSize) => {
    const value = classes(buttonVariants({ variant: "outline", size }));
    expect(value).toContain(radius);
    expect(value).toContain(iconSize);
    expect(value).not.toContain("rounded-lg");
    expect(value).not.toContain(ICON_SIZE_4);
  });

  it("keeps the base radius and icon size for regular sizes", () => {
    const value = classes(buttonVariants({ size: "default" }));
    expect(value).toContain("rounded-lg");
    expect(value).toContain(ICON_SIZE_4);
  });

  it("lets destructive focus styles replace the base focus styles", () => {
    const value = classes(buttonVariants({ variant: "destructive" }));
    expect(value).toContain("focus-visible:border-destructive/40");
    expect(value).toContain("focus-visible:ring-destructive/20");
    expect(value).not.toContain("focus-visible:border-ring");
    expect(value).not.toContain("focus-visible:ring-ring/50");
  });

  it("lets custom classes override conflicting variant and size classes", () => {
    const value = classes(buttonVariants({ size: "lg", className: "px-4 border-input" }));
    expect(value).toContain("px-4");
    expect(value).not.toContain("px-2.5");
    expect(value).toContain("border-input");
    expect(value).not.toContain("border-transparent");
  });
});

describe("Button", () => {
  it.each(VARIANTS.flatMap((variant) => (["default", "sm"] as const).map((size) => [variant, size] as const)))(
    "renders the same classes as a link styled with buttonVariants for %s / %s",
    (variant, size) => {
      render(
        <>
          <Button variant={variant} size={size}>
            Button
          </Button>
          <a href="/forecast" className={buttonVariants({ variant, size })}>
            Link
          </a>
        </>,
      );

      const button = classes(screen.getByRole("button", { name: "Button" }).className).sort();
      const link = classes(screen.getByRole("link", { name: "Link" }).className).sort();
      expect(button).toEqual(link);
    },
  );

  it("renders an outline border in the DOM", () => {
    render(<Button variant="outline">Retry</Button>);
    const button = classes(screen.getByRole("button", { name: "Retry" }).className);
    expect(button).toContain("border-border");
    expect(button).not.toContain("border-transparent");
  });

  it("applies a custom className over the variant classes", () => {
    render(
      <Button variant="outline" className="border-destructive">
        Delete
      </Button>,
    );
    const button = classes(screen.getByRole("button", { name: "Delete" }).className);
    expect(button).toContain("border-destructive");
    expect(button).not.toContain("border-border");
  });
});
