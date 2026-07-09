/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy /api/backend/* → http://localhost:8800/v1/* in dev.
  // The Authorization header is set on the client (same-origin → browser
  // forwards it). Set NEXT_PUBLIC_API_TOKEN in apps/web env (or .env.local).
  async rewrites() {
    const backend = process.env.BACKEND_URL || "http://127.0.0.1:8800";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backend}/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
