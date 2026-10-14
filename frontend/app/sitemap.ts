import type { MetadataRoute } from "next";

import {
  configuredSiteOrigin,
  PUBLIC_MARKETING_PATHS,
} from "@/lib/marketing-metadata";

/**
 * Emits absolute marketing URLs only when NEXT_PUBLIC_SITE_URL is a usable
 * public origin. Returns an empty list when the origin is missing or unusable
 * so localhost and preview hosts are never published.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const origin = configuredSiteOrigin();
  if (!origin) return [];

  return PUBLIC_MARKETING_PATHS.map((path) => ({
    url: new URL(path, `${origin}/`).toString(),
    changeFrequency: path === "/" || path === "/contact" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : 0.8,
  }));
}
