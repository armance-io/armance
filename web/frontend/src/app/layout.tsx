import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { ThemeProvider } from "@/lib/theme";
import { I18nBootstrap } from "@/components/visual/I18nBootstrap";

export const metadata: Metadata = {
  title: "Armance",
  description: "A house of minds, deliberating with you.",
  themeColor: "#6b4f8a",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ThemeProvider>
          <I18nBootstrap>{children}</I18nBootstrap>
        </ThemeProvider>
      </body>
    </html>
  );
}
