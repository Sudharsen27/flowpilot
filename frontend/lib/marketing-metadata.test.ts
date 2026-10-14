import { afterEach, describe, expect, it } from "vitest";

import {
  configuredSiteOrigin,
  marketingPageMetadata,
  PUBLIC_MARKETING_PATHS,
} from "@/lib/marketing-metadata";

const ORIGINAL = process.env.NEXT_PUBLIC_SITE_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = ORIGINAL;
});

describe("configuredSiteOrigin", () => {
  it("returns undefined when the site URL is missing", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    expect(configuredSiteOrigin()).toBeUndefined();
  });

  it("accepts a public http(s) origin", () => {
    expect(configuredSiteOrigin("https://www.example.com")).toBe(
      "https://www.example.com",
    );
    expect(configuredSiteOrigin("https://www.example.com/path")).toBe(
      "https://www.example.com",
    );
  });

  it("rejects localhost, credentials, and preview hosts", () => {
    expect(configuredSiteOrigin("http://localhost:3000")).toBeUndefined();
    expect(configuredSiteOrigin("http://127.0.0.1:3000")).toBeUndefined();
    expect(
      configuredSiteOrigin("https://user:pass@example.com"),
    ).toBeUndefined();
    expect(
      configuredSiteOrigin("https://flowpilot.vercel.app"),
    ).toBeUndefined();
    expect(configuredSiteOrigin("ftp://example.com")).toBeUndefined();
    expect(configuredSiteOrigin("not-a-url")).toBeUndefined();
  });
});

describe("marketingPageMetadata", () => {
  it("omits canonical and metadataBase when no site origin is configured", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    const metadata = marketingPageMetadata({
      title: "Product",
      description: "Lead context with human approval.",
      path: "/product",
    });
    expect(metadata.title).toBe("Product");
    expect(metadata.description).toMatch(/human approval/i);
    expect(metadata.alternates).toBeUndefined();
    expect(metadata.metadataBase).toBeUndefined();
    expect(metadata.openGraph).toMatchObject({
      title: "FlowPilot — Product",
      type: "website",
      siteName: "FlowPilot",
    });
    expect(metadata.openGraph && "url" in metadata.openGraph
      ? metadata.openGraph.url
      : undefined).toBeUndefined();
    expect(metadata.robots).toEqual({ index: true, follow: true });
  });

  it("sets canonical and Open Graph URLs for a valid public origin", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://www.example.com";
    const metadata = marketingPageMetadata({
      title: "Contact",
      description: "Request a FlowPilot demo.",
      path: "/contact",
    });
    expect(metadata.alternates).toEqual({
      canonical: "https://www.example.com/contact",
    });
    expect(metadata.metadataBase?.toString()).toBe("https://www.example.com/");
    expect(metadata.openGraph).toMatchObject({
      url: "https://www.example.com/contact",
    });
  });

  it("lists only public marketing paths for discovery", () => {
    expect(PUBLIC_MARKETING_PATHS).toEqual([
      "/",
      "/product",
      "/how-it-works",
      "/use-cases",
      "/contact",
    ]);
    expect(PUBLIC_MARKETING_PATHS).not.toContain("/login");
    expect(PUBLIC_MARKETING_PATHS).not.toContain("/dashboard");
  });
});
