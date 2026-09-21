// Política de rotas do proxy (allowlist). Módulo puro, sem dependências,
// para ser testável diretamente com `node --test`.
//
// PRINCÍPIO: o proxy injeta credenciais server-side; portanto NUNCA pode ser um
// relay aberto. Só passam rotas explicitamente listadas.

export const ALLOWED_GET = new Set([
  "health",
  "metrics",
  "brain/stats",
  "brain/episodes",
  "graph/topology",
]);

export const ALLOWED_POST = new Set([
  "chat",
]);

export function normalizePath(path) {
  return (path ?? [])
    .map((segment) => String(segment))
    .join("/")
    .replace(/^\/+|\/+$/g, "")
    .toLowerCase();
}

export function isAllowed(method, path) {
  const key = normalizePath(path);
  const verb = String(method ?? "").toUpperCase();
  if (verb === "GET" || verb === "HEAD") {
    return ALLOWED_GET.has(key);
  }
  if (verb === "POST") {
    return ALLOWED_POST.has(key);
  }
  return false;
}
