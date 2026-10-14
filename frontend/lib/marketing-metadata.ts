import type { Metadata } from "next";

/** Public marketing routes that may appear in a sitemap when a site origin is set. */
export const PUBLIC_MARKETING_PATHS = [
  "/",
  "/product",
  "/how-it-works",
  "/use-cases",
  "/contact",
] as const;

export type PublicMarketingPath = (typeof PUBLIC_MARKETING_PATHS)[number];

const PREVIEW_HOST_SUFFIXES = [
  ".vercel.app",
  ".netlify.app",
  ".pages.dev",
  ".ngrok-free.app",
  ".ngrok.app",
] as const;

function isUnusableHostname(hostname: string): boolean {
  const host = hostname.toLowerCase();
  if (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "0.0.0.0" ||
    host === "::1" ||
    host === "[::1]"
  ) {
    return true;
  }
  if (host.endsWith(".localhost")) return true;
  return PREVIEW_HOST_SUFFIXES.some((suffix) => host.endsWith(suffix));
}

/**
 * Returns a usable public site origin from NEXT_PUBLIC_SITE_URL, or undefined.
 * Localhost and common preview hosts are rejected so they are never published
 * as canonical or sitemap URLs.
 */
export function configuredSiteOrigin(
  raw = process.env.NEXT_PUBLIC_SITE_URL,
): string | undefined {
  const value = raw?.trim();
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return undefined;
    if (url.username || url.password) return undefined;
    if (!url.hostname || isUnusableHostname(url.hostname)) return undefined;
    return url.origin;
  } catch {
    return undefined;
  }
}

export function marketingPageMetadata({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: PublicMarketingPath;
}): Metadata {
  const origin = configuredSiteOrigin();
  const pageUrl = origin ? new URL(path, `${origin}/`).toString() : undefined;

  return {
    title,
    description,
    ...(origin ? { metadataBase: new URL(origin) } : {}),
    ...(pageUrl ? { alternates: { canonical: pageUrl } } : {}),
    openGraph: {
      title: `FlowPilot — ${title}`,
      description,
      type: "website",
      siteName: "FlowPilot",
      ...(pageUrl ? { url: pageUrl } : {}),
    },
    twitter: {
      card: "summary",
      title: `FlowPilot — ${title}`,
      description,
    },
    robots: {
      index: true,
      follow: true,
    },
  };
}
