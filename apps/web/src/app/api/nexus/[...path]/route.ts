import type { NextRequest } from "next/server";

import { isAllowed } from "../policy.mjs";

// Proxy server-side: mantém o Space PRIVADO e nunca expõe segredos ao browser.
// SEGURANÇA: allowlist explícita (policy.mjs). Como o proxy injeta credenciais,
// ele NUNCA pode atuar como relay aberto — rotas administrativas retornam 403.
// Variáveis (somente no servidor/Vercel — NUNCA em NEXT_PUBLIC_*):
//   NEXUS_SPACE_URL   ex.: https://usuario-space.hf.space
//   HF_TOKEN          token do Hugging Face (autentica o Space privado)
//   NEXUS_API_TOKEN   token interno da Nexus (header X-Nexus-Token)

const SPACE_URL = (process.env.NEXUS_SPACE_URL ?? "").replace(/\/$/, "");
const HF_TOKEN = process.env.HF_TOKEN ?? "";
const NEXUS_API_TOKEN = process.env.NEXUS_API_TOKEN ?? "";

async function forward(request: NextRequest, path: string[]): Promise<Response> {
  // Allowlist primeiro: bloqueia relay mesmo sem configuração.
  if (!isAllowed(request.method, path)) {
    return Response.json({ error: "forbidden_route" }, { status: 403 });
  }
  if (!SPACE_URL) {
    return Response.json({ error: "missing_config" }, { status: 500 });
  }

  const search = new URL(request.url).search;
  const target = `${SPACE_URL}/api/${path.join("/")}${search}`;

  const headers: Record<string, string> = {};
  if (HF_TOKEN) headers.Authorization = `Bearer ${HF_TOKEN}`;
  if (NEXUS_API_TOKEN) headers["X-Nexus-Token"] = NEXUS_API_TOKEN;
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  const init: RequestInit = { method: request.method, headers, cache: "no-store" };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  try {
    const upstream = await fetch(target, init);
    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return Response.json({ error: "upstream_unreachable" }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: { params: { path: string[] } }) {
  return forward(request, context.params.path);
}

export async function POST(request: NextRequest, context: { params: { path: string[] } }) {
  return forward(request, context.params.path);
}
