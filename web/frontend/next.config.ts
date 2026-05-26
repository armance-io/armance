import type { NextConfig } from "next";

const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  output: "standalone",
  experimental: {
    optimizePackageImports: ["@xyflow/react", "i18next", "react-i18next", "@tanstack/react-query"],
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${backend}/:path*` },
    ];
  },
};

export default config;
