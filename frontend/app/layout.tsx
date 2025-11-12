import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GhostEye v2 - Phishing Orchestrator",
  description: "Multi-conversation phishing simulation with human-realistic timing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

