/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    unoptimized: true,
  },
  // A Vercel não aceita o prefixo "PUBLIC" no nome da variável, mas o Next.js só
  // injeta no bundle do cliente variáveis com prefixo NEXT_PUBLIC_. Este mapeamento
  // expõe NEXT_PUBLISHABLE_NEXUS_API_URL sob o nome que o cliente consome.
  env: {
    NEXT_PUBLIC_NEXUS_API_URL:
      process.env.NEXT_PUBLISHABLE_NEXUS_API_URL ||
      process.env.NEXT_PUBLIC_NEXUS_API_URL ||
      "",
  },
};

module.exports = nextConfig;
