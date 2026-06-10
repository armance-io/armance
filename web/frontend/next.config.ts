import type { NextConfig } from "next";

const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

// ARMANCE_STATIC_EXPORT=1 → emit a static `out/` bundle (served by FastAPI in
// production, `armance web`). Unset → dev server with /api/* proxied to the
// backend for hot-reload iteration (`pnpm dev`).
const isExport = process.env.ARMANCE_STATIC_EXPORT === "1";

const config: NextConfig = isExport
  ? {
      output: "export",
      // The static host can't run the Next image optimizer.
      images: { unoptimized: true },
      experimental: {
        optimizePackageImports: ["@xyflow/react", "i18next", "react-i18next", "@tanstack/react-query"],
      },
    }
  : {
      // Next 16 blocks cross-origin dev resources (/_next/*) by default. The
      // Playwright E2E suite and local dev both hit the server via 127.0.0.1
      // and localhost; allow both so HMR + JS chunks load and the app hydrates.
      allowedDevOrigins: ["127.0.0.1", "localhost"],
      experimental: {
        optimizePackageImports: ["@xyflow/react", "i18next", "react-i18next", "@tanstack/react-query"],
      },
      async rewrites() {
        return [
          // Backend serves the API under /api; proxy straight through.
          { source: "/api/:path*", destination: `${backend}/api/:path*` },
          // Mirror the production FastAPI behaviour for dynamic routes: the
          // exported shell is pre-rendered with the "_" sentinel params and
          // real ids are read client-side from the URL (useRouteParams).
          // Without these, dev / `next start` 404s on any real id
          // (dynamicParams = false → NoFallbackError) and the E2E suite
          // cannot navigate anywhere.
          { source: "/projects/:pid/admin", destination: "/projects/_/admin" },
          { source: "/projects/:pid/sessions/:sid", destination: "/projects/_/sessions/_" },
          { source: "/projects/:pid/sessions/:sid/library", destination: "/projects/_/sessions/_/library" },
          { source: "/projects/:pid/sessions/:sid/deliverables", destination: "/projects/_/sessions/_/deliverables" },
          { source: "/projects/:pid/sessions/:sid/workflows/:name", destination: "/projects/_/sessions/_/workflows/_" },
          { source: "/projects/:pid/sessions/:sid/workflows/:name/preview", destination: "/projects/_/sessions/_/workflows/_/preview" },
          { source: "/projects/:pid/sessions/:sid/workflows/:name/runs/:runId", destination: "/projects/_/sessions/_/workflows/_/runs/_" },
          { source: "/projects/:pid", destination: "/projects/_" },
        ];
      },
    };

export default config;
