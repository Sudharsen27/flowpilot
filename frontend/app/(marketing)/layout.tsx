import type { ReactNode } from "react";

import { MarketingJsonLd } from "@/components/marketing/marketing-json-ld";

export default function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <MarketingJsonLd />
      {children}
    </div>
  );
}
