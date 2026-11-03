import type { NextConfig } from "next";

// DEMO_REPLAY=true serves recorded runs from app/demo-api for the hosted demo.
const api = process.env.DEMO_REPLAY === "true" ? "/demo-api" : (process.env.API_URL ?? "http://127.0.0.1:8000");

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
