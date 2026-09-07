// Next.js root config - zero-bundle split for HF deployment
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    missingSuspenseWithCSRBailout: false,
  },
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;
