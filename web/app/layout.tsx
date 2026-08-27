import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Navbar from "@/components/Navbar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "PackageSafe - npm, PyPI, and Maven package risk scanner",
    template: "%s | PackageSafe",
  },
  description:
    "Instant risk scores for any npm, PyPI, or Maven package. Catch typosquats, maintainer takeovers, and install-script surprises before they end up in your lockfile.",
  twitter: {
    card: "summary_large_image",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="bg-background font-sans text-foreground">
        <Navbar />
        {children}
      </body>
    </html>
  );
}
