# 🧩 AIO — AI Optimization (Nexus-Alpha)

**AIO** é o guarda-chuva da legibilidade e governança do projeto para **agentes
de IA em geral**: crawlers de treino, agentes de navegação, engines de resposta
([`AEO.md`](./AEO.md)) e generativos ([`GEO.md`](./GEO.md)). Complementa
[`SEO.md`](./SEO.md) (busca clássica) sem substituí-lo.

**Fronteira importante:** otimizar os *modelos internos* da Nexus-Alpha
(extração, refino, chat) **não** é AIO — isso vive em
[`RESEARCH.md`](./RESEARCH.md), [`ANALYTICS.md`](./ANALYTICS.md) e
[`TASKS.md`](./TASKS.md). AIO trata da superfície do projeto para IAs
externas, nos dois sentidos (como **editor** e como **consumidor**).

---

## 1. Como editor — postura atual e matriz de decisão

### Postura vigente (negado por padrão)
| Superfície | Política | Onde |
|---|---|---|
| Crawlers de IA (GPTBot, ChatGPT-User, PerplexityBot, ClaudeBot, Google-Extended, FacebookBot) | **bloqueados** (`Disallow: /`) | `public/robots.txt` |
| Buscadores clássicos | rotas sensíveis bloqueadas (`/api/`, `/_next/image*`, `/usage/`) | `public/robots.txt` |
| `/api/*` | `noindex, nofollow` + `nosniff` | `vercel.json` |
| Space (core FastAPI) | **privado**; só o proxy fala com ele | [`ADR-007`](./ADR.md) |

### Matriz de decisão para liberar um bot de IA
| Se o objetivo for… | Bot típico | Decisão padrão |
|---|---|---|
| Aparecer em RAG de resposta em tempo real | `PerplexityBot` | considerar liberar **só** a superfície pública estática |
| Ser citado no chat de LLMs | `ChatGPT-User`/`ClaudeBot` (navegação) | considerar, com ADR e superfície definida |
| Entrar em dataset de treino | `GPTBot`, `ClaudeBot` (treino), `Google-Extended` | **manter bloqueado** por padrão |
| Rede social/preview | `FacebookBot` | manter bloqueado (não é canal do produto) |

**Procedimento obrigatório para qualquer mudança:**
1. ADR descrevendo objetivo, superfície exposta e métrica de sucesso.
2. Ajuste de `public/robots.txt` (por User-Agent, nunca `*` liberando tudo).
3. Atualização do checklist do [`SEO.md`](./SEO.md) §5.
4. CI verde (allowlist do proxy intacta — nenhum segredo com `NEXT_PUBLIC_`).

## 2. Como editor — superfície machine-readable (o que já está certo)

1. **`GET /health`** é público e estável — o ponto de verificação canônico
   para qualquer agente/monitor ([`API.md`](./API.md)).
2. **`X-Robots-Tag: noindex, nofollow`** em `/api/*` impede que proxies
   públicos virem conteúdo indexável.
3. **Contratos estáveis:** API documentada ([`API.md`](./API.md)) e erros
   previsíveis ([`ERROR_HANDLING.md`](./ERROR_HANDLING.md)) — requisitos para
   qualquer consumidor programático.
4. **Nada de conteúdo só-em-JS** nas superfícies que decidirmos abrir:
   geradores de IA processam SSR/HTML estático com muito mais fidelidade
   (mesma lição do #048, do nosso lado consumidor).

### JSON-LD mínimo recomendado (quando houver superfície pública estável)
```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Nexus-Alpha",
  "description": "Motor de respostas factual baseado em grafo de conhecimento verificado por 3 domínios independentes.",
  "inLanguage": "pt-BR"
}
```

## 3. Como editor — `llms.txt` (proposta pronta)

Arquivo convencionado (`/llms.txt`) para descrever o site a LLMs. Hoje
**não existe** de propósito; se a postura mudar, usar este template
(criar em `public/llms.txt`):

```markdown
# Nexus-Alpha

> Motor de respostas factual: inteligência autônoma que verifica cada fato
> contra 3+ domínios independentes antes de consolidá-lo em grafo de
> conhecimento. Superfície pública: chat (pt-BR) e painel de saúde.

## Público
- / : chat conversacional extrativo (responde apenas com fatos verificados).

## Não é
- Não é produto de conteúdo; não há artigos/páginas de fatos públicos.
- /api/* é interno (proxy autenticado); o core (Hugging Face Space) é privado.

## Política de IA
- Crawlers de treino bloqueados (ver robots.txt). [ajustar conforme ADR]
```

Regras do `llms.txt`: honesto (descreve o que **é** e o que **não é**),
atualizado no mesmo PR que muda a superfície, sem segredo nem rota interna.

## 4. Como consumidor — AIO dos terceiros a nosso favor

1. **Respeitar `robots.txt`/`llms.txt` do alvo** é política de coleta
   ([`COMPLIANCE.md`](./COMPLIANCE.md) §2). `llms.txt` do alvo é sinal
   barato de "conteúdo aberto e estruturado para IA" — candidato futuro a
   critério de seed-quality ([`CONTENT.md`](./CONTENT.md) §2).
2. **Conteúdo machine-readable extrai melhor:** páginas declarativas/SSR
   rendem triplas; JS/listing rende zero (#048). Fontes estruturadas
   (API do Almanaque, #055) são o caminho natural do roadmap.
3. **Anti-bloqueio ≠ burla de AIO:** o `AntiBlockSystem` existe por causa do
   bloqueio em massa de IPs de datacenter; a política interna continua
   sendo conteúdo público, volume mínimo, sem burlar autenticação
   ([`COMPLIANCE.md`](./COMPLIANCE.md) §2).

## 5. Checklist de PR que toca AIO

- [ ] Mudança de política de crawler → ADR + `robots.txt` granular + `SEO.md` §5.
- [ ] `llms.txt` (se existir) atualizado junto com a superfície.
- [ ] Nenhuma rota interna exposta a agentes (Space segue privado; proxy intacto).
- [ ] Novas fontes de coleta: AIO de terceiros respeitado (robots/llms.txt).
- [ ] Sem objetivo de tráfego disfarçado — métrica de sucesso declarada no ADR.

## 6. Ver também

- [`SEO.md`](./SEO.md) — blindagem e indexação controlada (busca clássica).
- [`AEO.md`](./AEO.md) — respostas diretas (snippets/assistentes).
- [`GEO.md`](./GEO.md) — citação em engines generativos.
- [`COMPLIANCE.md`](./COMPLIANCE.md) — ética/legalidade da coleta e dados.
- [`ADR-007`](./ADR.md) — Space privado + proxy (base da postura de IA).
