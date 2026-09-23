# 🎯 AEO — Answer Engine Optimization (Nexus-Alpha)

**AEO** é a otimização para aparecer como **resposta direta** em mecanismos
de resposta: featured snippets, caixas "People Also Ask", assistentes de voz
e páginas de resposta de engines como Perplexity. É a camada entre
[`SEO.md`](./SEO.md) (busca clássica) e [`GEO.md`](./GEO.md) (citação em
geradores de IA).

---

## 1. Postura atual do projeto (editor) — negado por padrão

- `public/robots.txt` **bloqueia explicitamente** os crawlers de IA
  (`GPTBot`, `ChatGPT-User`, `PerplexityBot`, `ClaudeBot`, `Google-Extended`,
  `FacebookBot` com `Disallow: /`) e mantém `/api/`, `/_next/image*` e
  `/usage/` fechados para todos.
- `vercel.json` aplica `X-Robots-Tag: noindex, nofollow` em `/api/*`.

**Por quê:** a superfície pública existe para o chat e o painel; o valor do
produto (o grafo de fatos verificados) é privado e o Space é privado
([`ADR-007`](./ADR.md)). Não há página de conteúdo público para competir por
snippets — e está **ok** assim ([`SEO.md`](./SEO.md) §1).

## 2. Onde AEO já se aplica hoje: as respostas do chat

A única "resposta direta" que o Nexus-Alpha publica é a resposta do
`ChatWidget` — e ela já nasce sob princípios AEO por construção
([`ADR-008`](./ADR.md)):

| Princípio AEO | Como o chat cumpre |
|---|---|
| Resposta primeiro, contexto depois | geração **extrativa**: a frase factual vem à frente |
| Uma afirmação por frase | triplas viram frases atômicas (sujeito–predicado–objeto) |
| Entidades canônicas | refino determinístico (`canonicalizer`, caixa alta, aliases) |
| Rastreabilidade | resposta rastreável ao grafo; fonte preservada em `:FonteWeb` |
| Honestidade quando não há resposta | "não sei" é resposta válida (nunca inventar) |

**Instruções para evolução do chat** (mantêm AEO mesmo sem buscador):
1. Primeira frase da resposta = a afirmação factual completa (não saudação).
2. Nada de jargão interno (`db_status`, `fact_hash`) no texto ao visitante —
   metadados ficam no painel.
3. Datas/números no formato canônico do grafo (ex.: `1959`, não "em cerca de").

## 3. AEO como consumidor (o lado que interessa operacionalmente)

Mecanismos de resposta preferem conteúdo **declarativo e estruturado** — e a
Nexus-Alpha é, ela mesma, um mecanismo de resposta que consome a web:

1. Páginas em formato pergunta-resposta, definições diretas e listas factuais
   rendem triplas; páginas JS/listing rendem `entities_processed: 0`
   (lição medida no #048, ver [`RESEARCH.md`](./RESEARCH.md) R1).
2. Ao validar seeds novas ([`CONTENT.md`](./CONTENT.md) §2), priorize fontes
   com conteúdo declarativo — é o sinal AEO dos terceiros trabalhando a
   nosso favor.
3. Snippet ideal para extração: frase isolada com sujeito + verbo +
   complemento (é exatamente o que o `span_validator` consegue transformar
   em tripla sem fragmento).

## 4. Quando (e como) abrir a superfície para answer engines

Só com decisão registrada ([`ADR.md`](./ADR.md)) e na ordem:

1. **Decidir a superfície:** ex.: página pública estática (SSR) com os N
   fatos mais verificados — nunca expor `/api/` nem o Space.
2. **Formato answer-ready:** pergunta como heading (`H2`), resposta
   40–60 palavras logo abaixo, uma afirmação por frase.
3. **Dados estruturados:** `FAQPage`/`QAPage` JSON-LD (template abaixo).
4. **Crawler seletivo:** liberar **apenas** o bot necessário no
   `robots.txt` (ex.: permitir `Googlebot` para snippets mantendo
   `GPTBot`/`ClaudeBot` bloqueados) — e atualizar o checklist do
   [`SEO.md`](./SEO.md) §5 + o teste de allowlist do proxy no CI.
5. **Medir:** Search Console/contador de crawler em log — sem rastreio de
   usuários ([`COMPLIANCE.md`](./COMPLIANCE.md) §1).

### Template FAQPage (para uso futuro)

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [{
    "@type": "Question",
    "name": "Quem ergueu o Estádio Urbano Caldeira?",
    "acceptedAnswer": {
      "@type": "Answer",
      "text": "Fato verificado por 3 domínios independentes: <frase factual extraída do grafo>.",
      "url": "https://<domínio-fonte>/…"
    }
  }]
}
```

> ⚠️ Só cite no JSON-LD fatos com `verified_facts_domain_independent` — o
> JSON-LD é uma afirmação pública com a marca do projeto.

## 5. Checklist de PR que toca AEO

- [ ] Nenhuma resposta nova do chat quebra "afirmação primeiro".
- [ ] `robots.txt`/`vercel.json` alterados só com ADR + teste de CI atualizado.
- [ ] Novo conteúdo público (se existir) em formato pergunta→resposta com JSON-LD.
- [ ] Nenhum texto invisível/injetado para engines (anti-padrão ético —
      [`COMPLIANCE.md`](./COMPLIANCE.md) §2).
