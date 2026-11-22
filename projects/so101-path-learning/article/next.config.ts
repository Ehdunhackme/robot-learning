import type { NextConfig } from "next";
import { resolve } from "node:path";
const config: NextConfig = {
  trailingSlash: true,
  turbopack: { root: resolve(process.cwd(), "..") },
  async rewrites() {
    const studio = process.env.SO101_STUDIO_URL || "http://127.0.0.1:8766";
    return [{ source: "/api/arcbench/", destination: studio + "/api/run" }];
  },
};
export default config;
