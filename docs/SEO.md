# 🔎 SEO e Blindagem de Superfície Pública — Nexus-Alpha

O Nexus-Alpha **não é um produto de conteúdo para buscadores**: a superfície
pública (frontend Next.js na Vercel) existe para o chat e o painel. O objetivo
aqui é **indexação controlada** e **blindagem** contra scrapers e enumeração
de rotas sensíveis.

---

## 1. Postura de indexação

- `public/robots.txt` **bloqueia** rotas sensíveis e bots agressivos
  (ver arquivo em `public/robots.txt`).
- `vercel.json` aplica headers de segurança e bloqueio de rotas:
  `/api/*` e `/_next/image*` não são expostos publicamente.
- Não há sitemap gerado nem meta-tags de otimização de busca — prioridade é
  privacidade do grafo, não tráfego orgânico.

## 2. Rotas e exposição

| Rota | Exposição | Nota |
|---|---|---|
| `/` (frontend) | pública | chat + painel; sem dados sensíveis |
| `/api/nexus/[...path]` | pública (proxy) | repassa ao Space privado com segredos server-side |
| Space HF (`*.hf.space`) | **privado** | só o proxy tem `NEXUS_SPACE_URL`+`HF_TOKEN`+`NEXUS_API_TOKEN` |
| `/api/*` direto no Vercel | bloqueada via `vercel.json` + robots | anti-enumeração |

## 3. Regras para novas rotas públicas

1. Toda rota nova no Next.js precisa estar coberta pelas regras de
   `robots.txt`/`vercel.json` (ou explicitamente liberada com justificativa).
2. Nenhuma rota pública pode revelar métricas internas brutas — dados de
   `/api/metrics` chegam ao UI **via proxy autenticado**, nunca expostos
   como endpoint público sem filtro.
3. Headers de segurança obrigatórios no proxy (mesma política do
   `vercel.json`): anti-clickjacking, no-sniff, referrer-policy restritiva.
4. O allowlist do proxy é validada no CI (passo 8 do gate, Node 20) —
   alterá-la exige atualizar o teste.

## 4. Conteúdo minerado × republicação

- O conteúdo coletado é matéria-prima interna (triplas), **não republicado**.
  Não há página pública de "fatos" — apenas consulta conversacional.
- Respeito a `robots.txt` dos sites minerados é tratado na camada de coleta
  e conformidade — ver [`COMPLIANCE.md`](./COMPLIANCE.md).

## 6. Descoberta por IA (AEO/GEO/AIO)

A postura de indexação controlada se estende aos motores de IA — hoje com
**bloqueio explícito** dos crawlers de IA no `robots.txt`. Para as camadas
específicas, ver:

- [`AEO.md`](./AEO.md) — respostas diretas (snippets, assistentes).
- [`GEO.md`](./GEO.md) — citação em engines generativos (ChatGPT, Perplexity).
- [`AIO.md`](./AIO.md) — guarda-chuva: política de crawlers de IA, `llms.txt`
  e legibilidade para agentes.

## 7. Checklist de PRs que tocam a superfície pública

- [ ] `public/robots.txt` atualizado se a rota mudar.
- [ ] `vercel.json` validado (headers + bloqueios mantidos).
- [ ] Teste do allowlist do proxy atualizado (CI Node).
- [ ] Nenhum segredo com prefixo `NEXT_PUBLIC_`.
- [ ] Título/descrição da página consistentes com a marca (grafite/roxo, pt-BR).
