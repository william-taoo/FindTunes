import type { NextConfig } from "next";

const backendUrl = process.env.FINDTUNES_BACKEND_URL;

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1'],
  env: {
    NEXT_PUBLIC_DOMAIN: backendUrl || process.env.VERCEL === '1'
      ? '/api/backend'
      : process.env.NEXT_PUBLIC_DOMAIN || 'http://localhost:8000',
  },
  async rewrites() {
    if (!backendUrl) return [];

    const backend = new URL(backendUrl);
    if (backend.protocol !== 'https:' && backend.protocol !== 'http:') {
      throw new Error('FINDTUNES_BACKEND_URL must be an HTTP or HTTPS URL');
    }

    return [{ source: '/api/backend/:path*', destination: `${backend.origin}/:path*` }];
  },
};

export default nextConfig;
