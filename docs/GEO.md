# 🤖 GEO — Generative Engine Optimization (Nexus-Alpha)

**GEO** é a otimização para ser **citado e usado como fonte** por motores
generativos (ChatGPT, Perplexity, Gemini, Copilot e afins). Onde
[`AEO.md`](./AEO.md) mira a resposta direta, GEO mira a citação dentro de
respostas geradas por IA.

---

## 1. Estado atual: não somos citáveis — por decisão

- `public/robots.txt` bloqueia `GPTBot`, `ChatGPT-User`, `PerplexityBot`,
  `ClaudeBot` e `Google-Extended` (`Disallow: /`) — ou seja: treino,
  navegação e RAG dos generativos estão **fora** hoje.
- Isto é coerente com a postura do [`SEO.md`](./SEO.md): o site não é produto
  de conteúdo; o grafo é privado; o Space é privado ([`ADR-007`](./ADR.md)).

**A pergunta GEO correta não é "como ser citado?" e sim "vale a pena ser
citado?".** Para o Nexus-Alpha, a resposta hoje é não — exposição de fatos
sem uma decisão de produto diluiria o diferencial (verificação por 3 domínios)
em troca de tráfego que não é objetivo.

## 2. O que já somos: um gerador com higiene de citação

O chat da Nexus-Alpha **é um generative engine em miniatura** — e segue os
princípios que exigiríamos de terceiros:

| Princípio GEO (para engines) | Como a Nexus-Alpha cumpre |
|---|---|
| Citar fontes das afirmações | resposta extrativa rastreável ao grafo; `source_url` preservada em `:FonteWeb` |
| Só afirmar o verificável | quórum de **3 domínios independentes** ([`ADR-003`](./ADR.md)) |
| Frescura do fato | `last_seen_at` indexado; `replays` marca recorrência |
| Não plagiar volume | armazenamos **triplas factuais**, nunca republicamos texto ([`COMPLIANCE.md`](./COMPLIANCE.md) §2) |

Isto importa porque, se um dia abrirmos uma superfície pública, ela já
nasce citável por construção — sem retrabalho.

## 3. O que torna um fato do grafo "citável" (padrão interno)

Definição operacional para uso futuro (e para o QA do conteúdo):

1. **Verificado por domínio independente** — `verified_facts_domain_independent`,
   nunca a métrica legada por URL (#049).
2. **Atômico** — sujeito/objeto são entidades, não fragmentos
   (`span_validator` aprovou; nada de "EM 1959" como objeto).
3. **Predicado canônico** — vocabulário controlado, caixa alta
   ([`CONTENT.md`](./CONTENT.md) §4).
4. **Atribuído** — ao menos uma `:FonteWeb` de publisher reputável
   (`REPUTABLE_PUBLISHERS`, #056).
5. **Vivo** — `last_seen_at` recente; fatos não reconfirmados em janela longa
   perdem prioridade de exposição.

## 4. Roteiro de abertura (só com ADR)

Se o produto decidir expor fatos para generativos, nesta ordem:

1. **Superfície estática legível sem JS** (SSR/HTML puro) com os fatos
   aprovados no §3 — generativos processam HTML simples melhor que SPA.
2. **`public/llms.txt`** descrevendo o projeto e as rotas públicas
   (template em [`AIO.md`](./AIO.md) §3).
3. **Dados estruturados por fato:** `schema.org/Claim` (ou `Dataset`) com
   `citation` apontando à fonte original — jamais como afirmação sem fonte.
4. **Política de crawler granular:** liberar o mínimo (ex.: `PerplexityBot`
   para RAG em tempo real) mantendo bloqueio de treino (`GPTBot`,
   `Google-Extended`) se essa for a decisão — atualizar `robots.txt`,
   [`SEO.md`](./SEO.md) §5 e o teste do CI.
5. **Medição por log de crawler** (qual bot bateu, quanto) — sem rastreio de
   usuário ([`COMPLIANCE.md`](./COMPLIANCE.md) §1).
6. **Endpoint público read-only** de fatos verificados, se houver, com quota
   e sem autenticação no Space (proxy only) — novo ADR obrigatório.

## 5. Anti-padrões éticos (proibidos)

1. **Prompt injection em conteúdo** — texto invisível ("ignore instruções
   anteriores") para manipular LLMs que leiam a página. É o mesmo crime que
   o nosso `TriangulationFilter` combate na entrada.
2. **Comprar inclusão em datasets/feeds de treino** — fora da política de
   custo zero e de integridade.
3. **Expor fato não verificado como se verificado** — contamina a marca de
   verificação, o ativo central do projeto.
4. **Liberar crawler de IA para "ver se sobe tráfego"** sem métrica nem ADR —
   viola [`RULES.md`](./RULES.md) §1.

## 6. GEO como consumidor (reciprocidade)

Quando a Nexus-Alpha minera, ela se beneficia do GEO dos outros:

1. **Fontes citáveis/primárias** já estão na allowlist
   (`REPUTABLE_PUBLISHERS`, `.org`/`.edu`/`.gov`) — o mesmo critério que um
   ChatGPT usaria para citar.
2. **Conteúdo com citação embutida** (páginas que referenciam fontes) tende a
   gerar triplas corroboráveis — preferir na validação de seeds
   ([`CONTENT.md`](./CONTENT.md) §2).
3. **Respeito a `llms.txt`/robots de terceiros** é parte da coleta —
   [`COMPLIANCE.md`](./COMPLIANCE.md) §2; leitura de `llms.txt` do alvo é
   sinal barato de "conteúdo aberto para IA" (futuro item de seed-quality).

## 7. Checklist de PR que toca GEO

- [ ] Nenhuma mudança libera crawler de IA sem ADR + `robots.txt` + teste.
- [ ] Qualquer fato exposto publicamente cumpre os 5 critérios do §3.
- [ ] Sem conteúdo invisível/injetado; sem republicação de texto de terceiros.
- [ ] Atribuição de fonte presente em qualquer afirmação pública.
