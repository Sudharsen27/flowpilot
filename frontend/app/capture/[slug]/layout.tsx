import type { ReactNode } from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Contact us",
};

export default function CaptureLayout({ children }: { children: ReactNode }) {
  return children;
}
