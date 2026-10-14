import { render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarketingJsonLd } from "@/components/marketing/marketing-json-ld";

const ORIGINAL = process.env.NEXT_PUBLIC_SITE_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = ORIGINAL;
});

function scriptsJson() {
  return Array.from(document.querySelectorAll('script[type="application/ld+json"]')).map(
    (node) => JSON.parse(node.textContent || "{}"),
  );
}

describe("MarketingJsonLd", () => {
  it("emits Organization data without inventing a site URL", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    render(<MarketingJsonLd />);
    const payloads = scriptsJson();
    expect(payloads).toHaveLength(1);
    expect(payloads[0]).toMatchObject({
      "@type": "Organization",
      name: "FlowPilot",
      email: "hello.sundardigital@gmail.com",
      parentOrganization: {
        name: "Sundar Digital",
        url: "https://www.sundardigital.in/",
      },
    });
    expect(payloads[0].url).toBeUndefined();
    expect(JSON.stringify(payloads)).not.toMatch(/<\/script>/i);
  });

  it("adds WebSite structured data when a public origin is configured", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://www.example.com";
    render(<MarketingJsonLd />);
    const payloads = scriptsJson();
    expect(payloads).toHaveLength(2);
    expect(payloads[0]).toMatchObject({
      "@type": "Organization",
      url: "https://www.example.com",
    });
    expect(payloads[1]).toMatchObject({
      "@type": "WebSite",
      name: "FlowPilot",
      url: "https://www.example.com",
    });
  });
});
