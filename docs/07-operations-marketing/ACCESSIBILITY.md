# ♿ Acessibilidade — Nexus-Alpha

Aplica-se ao frontend Next.js (`src/frontend/`, `src/app/`), ao widget de
chat e ao dashboard Streamlit. Meta: **WCAG 2.1 nível AA** nas superfícies
interativas.

---

## 1. Regras obrigatórias

| Requisito | Como cumprir | Onde |
|---|---|---|
| Contraste AA (≥4.5:1 texto) | paleta grafite/roxo validada; texto secundário `#94A3B8` só em metadados ≥14px | [`DESIGN.md`](./DESIGN.md) |
| Foco visível | borda roxa `#8B5CF6` 2px em todo elemento focável; nunca `outline: none` sem substituto | todos os componentes |
| Navegação por teclado | chat operável 100% via teclado: abrir, digitar, enviar, ler histórico (Tab/Enter/Shift+Tab) | `ChatWidget.tsx` |
| `aria-live` | novas mensagens do bot anunciadas (`aria-live="polite"`); estado "Nexus pensando…" anunciado | `ChatWidget.tsx` |
| Rótulos | inputs com `label`/`aria-label` em pt-BR; botão de envio com nome acessível | formulários |
| Reduced motion | respeitar `prefers-reduced-motion`: desligar pulsos/skeletons animados e transições do Motion | `motion.config.ts` |
| Semântica | landmarks (`main`, `nav`), headings hierárquicos, `lang="pt-BR"` em `layout.tsx` | `src/app/layout.tsx` |
| Alternativas | gráfico de força precisa de tabela/`sr-only` equivalente com os nós principais | `KnowledgeGraph.tsx` |

## 2. Painéis de dados (BrainPanel, Dashboard)

1. Todo número-chave acompanhado do **limiar textual** (ex.:
   `retention_pressure: low (menos de 50% de 10k)`) — cor nunca é o único
   portador de significado (status ok/warn/error sempre com rótulo).
2. Tabelas com `<th>` escopo correto; contraste em células de status.
3. Estados de fallback (`source: volatile`, `db_status: demo-memory`)
   anunciados em texto, não só por cor.

## 3. ChatWidget — checklist específico

- [ ] Bolha flutuante é `<button>` com `aria-expanded` e `aria-controls`.
- [ ] Histórico com `role="log"` + `aria-live="polite"`.
- [ ] Envio por Enter; quebra de linha por Shift+Enter (se suportada).
- [ ] Skeleton "Nexus pensando…" tem `aria-hidden` + texto alternativo
      anunciado uma única vez.
- [ ] Erros de rede em texto legível ("Não foi possível falar com a Nexus.
      Tente novamente.") — nunca só cor/ícone.

## 4. Dashboard Streamlit

- Tema escuro com contraste validado; sem rely-on-color nos status.
- Gráficos com título e rótulos de eixo em pt-BR.

## 5. Processo

1. Acessibilidade é critério de aceite em PRs de UI (ver
   [`CODE_REVIEW.md`](./CODE_REVIEW.md) — checklist UI).
2. QA manual com teclado + leitor de tela (NVDA/VoiceOver) em toda mudança
   do chat — roteiro em [`QA_TESTING.md`](./QA_TESTING.md).
3. Novo componente sem checklist acessível **não** mergea.
