/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Proxy API routes to the Python backend during dev
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.BACKEND_URL || "http://localhost:8800"}/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
