import type { ReactNode } from "react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chat with us",
};

export default function ChatCaptureLayout({ children }: { children: ReactNode }) {
  return children;
}
