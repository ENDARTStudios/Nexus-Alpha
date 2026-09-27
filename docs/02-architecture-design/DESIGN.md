# 🎨 Design System — Nexus-Alpha

Aplica-se ao frontend Next.js (`src/frontend/`, `src/app/`), ao widget de
chat e ao dashboard Streamlit (`dashboard/app.py`).

---

## 1. Identidade

Tema **escuro técnico** ("grafite elétrico"): superfícies escuras, acento
roxo elétrico, tipografia de sistema, movimento sutil via Motion (Framer).

## 2. Cores

| Token | Valor | Uso |
|---|---|---|
| `surface` | `#0F172A` (grafite) | fundo principal (slate-900) |
| `surface-raised` | `#1E293B` (slate-800) | cards, bolhas de mensagem |
| `border-accent` | `#8B5CF6` (roxo elétrico) | bordas de destaque, foco, CTA |
| `accent` | `#8B5CF6` | links, indicadores ativos |
| `accent-soft` | roxo com alpha ~12% | hovers, skeletons |
| `text-primary` | `#F8FAFC` (slate-50) | texto principal |
| `text-secondary` | `#94A3B8` (slate-400) | metadados, timestamps |
| `status-ok` | verde (emerald-500) | saúde `ok`, grafo conectado |
| `status-warn` | âmbar (amber-500) | `degraded`, fallback volátil |
| `status-error` | vermelho (rose-500) | `down`, quarentena cheia |

Regras: contraste mínimo AA (4.5:1) para texto; roxo nunca usado em texto
corrido longo — só acento. Status segue os campos de `db_status`/`source`
da API (`demo-memory` → warn; `neo4j` → ok).

## 3. Tipografia

- **Fonte:** stack de sistema (`system-ui`/Tailwind default) — zero webfont
  (performance e custo zero).
- **Escala:** base 16px; títulos do dashboard 20–28px; mono para
  `fact_hash`, Cypher e payloads (`font-mono`).

## 4. Movimento (Motion)

Config centralizada em `src/frontend/lib/motion.config.ts`:

- Entrada de mensagens do chat: fade + translateY(8px), ~180ms, easing suave.
- Indicador "Nexus pensando…": pulso de opacidade no skeleton (loop).
- Grafo de conhecimento: simulação de física do `react-force-graph-2d`
  com cooldown; sem animação decorativa em listas densas.
- `prefers-reduced-motion`: desabilitar transações não essenciais
  (ver [`ACCESSIBILITY.md`](./ACCESSIBILITY.md)).

## 5. Componentes

| Componente | Arquivo | Notas |
|---|---|---|
| `ChatWidget` | `src/frontend/components/ChatWidget.tsx` | bolha flutuante; tema grafite + borda roxa; skeletons por mensagem; histórico curto por `session_id` |
| `Dashboard` | `src/frontend/components/Dashboard.tsx` | agregador de painéis; consome proxy `/api/nexus/*` |
| `BrainPanel` | `src/frontend/components/BrainPanel.tsx` | **read-only**; contrato normalizado de `/api/brain/stats`; mostra `source` (neo4j/volatile) |
| `KnowledgeGraph` | `src/frontend/components/KnowledgeGraph.tsx` | `react-force-graph-2d` sobre `/api/graph/topology` |
| API client | `src/frontend/lib/api.ts` / `nexus.ts` / `brain.ts` | única porta de entrada HTTP; nenhum fetch direto em componente |

## 6. Padrões de UX

1. **Estado sempre visível:** todo painel mostra origem e saúde
   (`db_status`, `source`, `cognitive_health`) — nunca silêncio.
2. **Degradar com honestidade:** fallback (`volatile`, `demo-memory`) é
   exibido como aviso, não escondido.
3. **Feedback de carregamento:** skeletons antes de spinners.
4. **Erros:** mensagem curta em pt-BR + ação sugerida ("tentar novamente"),
   sem stack traces no UI.
5. **Densidade:** painéis técnicos priorizam tabela compacta sobre cards
   grandes; números-chave sempre com unidade/limiar (ex.: `retention_pressure: low (<50%)`).

## 7. Dashboard Streamlit

`dashboard/app.py` opera em modo escuro (`st.set_page_config` + tema),
com as mesmas cores e leitura das mesmas métricas — é a superfície do
operador; o Next.js é a superfície do visitante.

## 8. Acessibilidade

Obrigatória: contraste AA, foco visível (borda roxa 2px), navegação por
teclado no chat, `aria-live` nas mensagens. Detalhes em
[`ACCESSIBILITY.md`](./ACCESSIBILITY.md).
