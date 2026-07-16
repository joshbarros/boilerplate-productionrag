/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Per-niche proxy: /api/<niche>/* → http://localhost:<port>/v1/*.
  // Using a same-origin proxy lets the browser forward the Authorization
  // header without CORS preflight (the niche backends don't enable CORS
  // by default — they sit behind the same-origin dev proxy).
  async rewrites() {
    const core = process.env.CORE_BACKEND_URL || "http://127.0.0.1:8800";
    const medical = process.env.MEDICAL_BACKEND_URL || "http://127.0.0.1:8810";
    const legal = process.env.LEGAL_BACKEND_URL || "http://127.0.0.1:8820";
    const accounting =
      process.env.ACCOUNTING_BACKEND_URL || "http://127.0.0.1:8830";
    return [
      { source: "/api/core/:path*", destination: `${core}/v1/:path*` },
      { source: "/api/medical/:path*", destination: `${medical}/v1/:path*` },
      { source: "/api/legal/:path*", destination: `${legal}/v1/:path*` },
      {
        source: "/api/accounting/:path*",
        destination: `${accounting}/v1/:path*`,
      },
      // Legacy default (kept so the root generic still works without
      // explicit niche switching).
      { source: "/api/backend/:path*", destination: `${core}/v1/:path*` },
    ];
  },
};

module.exports = nextConfig;
