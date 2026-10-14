import type { MetadataRoute } from "next";

import { configuredSiteOrigin } from "@/lib/marketing-metadata";

/** App and auth surfaces that must not be advertised for indexing. */
const DISALLOW = [
  "/dashboard",
  "/login",
  "/register",
  "/leads",
  "/agents",
  "/inbox",
  "/approvals",
  "/activity",
  "/analytics",
  "/integrations",
  "/knowledge",
  "/workflows",
  "/settings",
  "/capture/",
] as const;

export default function robots(): MetadataRoute.Robots {
  const origin = configuredSiteOrigin();

  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [...DISALLOW],
    },
    ...(origin ? { sitemap: `${origin}/sitemap.xml` } : {}),
  };
}
