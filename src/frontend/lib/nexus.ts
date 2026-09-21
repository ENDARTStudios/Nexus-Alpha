// Resolve a base da API da Nexus.
//
// - Padrão (Space privado): proxy server-side em `/api/nexus/*` (Vercel).
// - Modo direto (Space público): defina NEXT_PUBLIC_NEXUS_API_URL.
//
// O proxy mantém HF_TOKEN/NEXUS_API_TOKEN exclusivamente no servidor.

const DIRECT = (process.env.NEXT_PUBLIC_NEXUS_API_URL ?? "").replace(/\/$/, "");

export const NEXUS_BASE = DIRECT ? `${DIRECT}/api` : "/api/nexus";

export function nexusUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${NEXUS_BASE}${suffix}`;
}
