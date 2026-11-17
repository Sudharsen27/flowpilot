import type { NextConfig } from "next";

/**
 * Production on Vercel should call the API same-origin (`/api/...`) and rewrite
 * to Render. That makes the session cookie first-party on the Vercel host so
 * Chrome accepts it. Cross-site `vercel.app` → `onrender.com` cookies are
 * blocked even with SameSite=None.
 *
 * Set `API_PROXY_TARGET` to the Render origin (no path), for example
 * `https://flowpilot-backend-product.onrender.com`. Leave unset for local
 * `next dev` when the browser talks to localhost:8000 directly.
 */
function apiProxyRewrites(): { source: string; destination: string }[] {
  const target = process.env.API_PROXY_TARGET?.trim().replace(/\/$/, "");
  if (!target) {
    return [];
  }
  return [
    {
      source: "/api/:path*",
      destination: `${target}/api/:path*`,
    },
  ];
}

const nextConfig: NextConfig = {
  async rewrites() {
    return apiProxyRewrites();
  },
};

export default nextConfig;
