import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // `standalone` emits a self-contained server bundle under
  // `.next/standalone/` that includes only the node_modules actually
  // imported. It's the build mode the Dockerfile copies into the
  // runtime stage, which keeps the final image ~50MB instead of
  // shipping the entire monorepo. Local `pnpm dev` ignores this.
  output: "standalone",
};

export default nextConfig;
