import { afterEach, describe, expect, it } from "vitest";

import sitemap from "@/app/sitemap";

const ORIGINAL = process.env.NEXT_PUBLIC_SITE_URL;

afterEach(() => {
  if (ORIGINAL === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = ORIGINAL;
});

describe("sitemap", () => {
  it("returns no entries when the site origin is missing or unusable", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    expect(sitemap()).toEqual([]);

    process.env.NEXT_PUBLIC_SITE_URL = "https://preview.vercel.app";
    expect(sitemap()).toEqual([]);
  });

  it("lists only intended public marketing routes for a valid origin", () => {
    process.env.NEXT_PUBLIC_SITE_URL = "https://www.example.com";
    const entries = sitemap();
    const urls = entries.map((entry) => entry.url);
    expect(urls).toEqual([
      "https://www.example.com/",
      "https://www.example.com/product",
      "https://www.example.com/how-it-works",
      "https://www.example.com/use-cases",
      "https://www.example.com/contact",
    ]);
    expect(urls.join(" ")).not.toMatch(/login|register|dashboard|leads|api/i);
  });
});
