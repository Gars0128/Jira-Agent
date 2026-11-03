import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tiro — from client call to Jira",
  description: "Trace requirements to client evidence, review user stories, and approve a Jira preview.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
