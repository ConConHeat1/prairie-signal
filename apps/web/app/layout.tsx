import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

const siteName = process.env.NEXT_PUBLIC_APP_NAME ?? "Prairie Signal";

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: {
    default: `${siteName} — Lincoln weather from official sources`,
    template: `%s — ${siteName}`,
  },
  description:
    "A calm, ad-free view of current conditions, official NWS alerts, and forecasts for Lincoln and the central Great Plains.",
  applicationName: siteName,
  category: "weather",
  robots: { index: false, follow: false },
  openGraph: {
    type: "website",
    title: siteName,
    description:
      "Official NWS conditions and forecasts, with freshness shown clearly.",
    siteName,
    images: [
      {
        url: "/prairie-signal-og.png",
        width: 1200,
        height: 630,
        alt: `${siteName} — a clear view of Great Plains weather`,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteName,
    description:
      "Official NWS conditions and forecasts, with freshness shown clearly.",
    images: ["/prairie-signal-og.png"],
  },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#0a2531",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
