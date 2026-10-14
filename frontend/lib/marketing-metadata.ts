import type { Metadata } from "next";

function configuredSiteOrigin(): string | undefined {
  const raw = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!raw) return undefined;
  try {
    const url = new URL(raw);
    if (url.protocol !== "https:" && url.protocol !== "http:") return undefined;
    if (url.username || url.password) return undefined;
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
  path: `/${string}`;
}): Metadata {
  const origin = configuredSiteOrigin();
  const pageUrl = origin ? new URL(path, origin).toString() : undefined;

  return {
    title,
    description,
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
  };
}
