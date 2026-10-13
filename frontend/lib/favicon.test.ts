import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { metadata as marketingMetadata } from "@/app/(marketing)/page";

function pngSize(path: string) {
  const buf = readFileSync(path);
  expect(buf.subarray(0, 8)).toEqual(
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
  );
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

describe("FlowPilot favicon assets", () => {
  it("ships crisp 16, 32, and 48 pixel symbol marks", () => {
    expect(pngSize(resolve("public/favicon-16x16.png"))).toEqual({
      width: 16,
      height: 16,
    });
    expect(pngSize(resolve("public/favicon-32x32.png"))).toEqual({
      width: 32,
      height: 32,
    });
    expect(pngSize(resolve("public/favicon-48x48.png"))).toEqual({
      width: 48,
      height: 48,
    });
    expect(pngSize(resolve("app/icon.png"))).toEqual({
      width: 192,
      height: 192,
    });

    const ico = readFileSync(resolve("app/favicon.ico"));
    expect(ico.subarray(0, 4)).toEqual(Buffer.from([0, 0, 1, 0]));
    expect(ico[4]).toBe(3);
  });

  it("keeps the public homepage title", () => {
    expect(marketingMetadata.title).toBe("AI Sales Operations Platform");
  });
});
