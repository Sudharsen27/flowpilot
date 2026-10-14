import { afterEach, describe, expect, it } from "vitest";

import robots from "@/app/robots";

const ORIGINAL = process.env.NEXT_PUBLIC_SITE_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = ORIGINAL;
});

describe("robots", () => {
  it("allows marketing discovery and blocks authenticated app routes", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    const result = robots();
    expect(result.rules).toMatchObject({
      userAgent: "*",
      allow: "/",
    });
    const disallow = Array.isArray(result.rules)
      ? result.rules[0]?.disallow
      : result.rules.disallow;
    expect(disallow).toEqual(
      expect.arrayContaining([
        "/dashboard",
        "/login",
        "/register",
        "/leads",
        "/settings",
        "/capture/",
      ]),
    );
    expect(result.sitemap).toBeUndefined();
  });

  it("publishes a sitemap URL only for a usable public origin", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://www.example.com";
    expect(robots().sitemap).toBe("https://www.example.com/sitemap.xml");

    process.env.NEXT_PUBLIC_SITE_URL = "http://localhost:3000";
    expect(robots().sitemap).toBeUndefined();
  });
});
