import { configuredSiteOrigin } from "@/lib/marketing-metadata";

const ORGANIZATION_DESCRIPTION =
  "FlowPilot is an AI sales operations workspace that keeps lead context, qualification, response drafts, human approval, explicit sending, and follow-ups on one organization record.";

/**
 * Verified Organization and optional WebSite structured data.
 * Uses only product facts already present in the repository.
 * WebSite.url is omitted when NEXT_PUBLIC_SITE_URL is not a usable origin.
 */
export function MarketingJsonLd() {
  const origin = configuredSiteOrigin();

  const organization = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "FlowPilot",
    description: ORGANIZATION_DESCRIPTION,
    email: "hello.sundardigital@gmail.com",
    ...(origin ? { url: origin } : {}),
    parentOrganization: {
      "@type": "Organization",
      name: "Sundar Digital",
      url: "https://www.sundardigital.in/",
    },
  };

  const website = origin
    ? {
        "@context": "https://schema.org",
        "@type": "WebSite",
        name: "FlowPilot",
        url: origin,
        description: ORGANIZATION_DESCRIPTION,
        publisher: {
          "@type": "Organization",
          name: "FlowPilot",
        },
      }
    : null;

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(organization) }}
      />
      {website ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(website) }}
        />
      ) : null}
    </>
  );
}
