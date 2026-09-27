# 🕵️ QA Testing — Validação funcional pré-produção (Nexus-Alpha)

QA aqui é **funcional + integridade de conhecimento**: o objetivo não é
"o botão parece bonito", é "o cérebro não corrompeu nada".

---

## 1. Roteiro de QA (executar a cada release/ciclo relevante)

### A. Saúde do core (Space)
- [ ] `GET /health` → 200 com estado esperado.
- [ ] `GET /api/metrics` → blocos presentes: `cognitive_health`,
      `extraction_quality`, `verification`, `ingestion_accounting`, `quarantine`.
- [ ] `cognitive_health.hebbian_consistency_check = true`.
- [ ] `ingestion_accounting.accounting_mode` conhecido (`exact` ou overflow
      justificado).

### B. Ingest e integridade
- [ ] Ingest autenticado com payload pequeno → resposta com contadores.
- [ ] Payload > 1MB → **rejeitado** (interceptor).
- [ ] Token inválido → 401/403, sem detalhes internos na mensagem.
- [ ] 11 tentativas seguidas com token errado → bloqueio (brute-force).
- [ ] Sem Neo4j (simular): resposta usa `db_status: "demo-memory"` e nada
      é perdido (quarentena/aguardando).

### C. Conhecimento (o coração do QA)
- [ ] Fato rejeitado aparece na quarentena **com motivo tipado** (ex.:
      objeto `EM 1959` → `object_date_like`).
- [ ] `top_invalid_predicates` vazio ou só com lixo novo explicável.
- [ ] Repetir ingest do mesmo fato no mesmo dia → `replays` incrementa,
      contagem de episódios **não** infla.
- [ ] `verified_facts` só cresce com `duplicate_cross_domain` (nunca
      same-domain/same-url).

### D. Chat (frontend + API)
- [ ] Pergunta com fato verificado no grafo → resposta extrativa coerente.
- [ ] Pergunta sem fato → resposta honesta (sem invenção).
- [ ] 6 requisições em 1 minuto do mesmo IP → 429 na sexta.
- [ ] Rede derrubada → mensagem amigável + retry, sem travar o widget.
- [ ] "Nexus pensando…" aparece e some; mensagens anunciadas (aria-live).

### E. Painéis
- [ ] BrainPanel reflete `/api/brain/stats`; BrainPanel **read-only**
      (nenhum botão de escrita).
- [ ] Estados de fallback visíveis (`source: volatile`, `demo-memory`).
- [ ] KnowledgeGraph carrega topologia sem travar o navegador.

### F. Acessibilidade (superfície de visitante)
- [ ] Navegação completa do chat por teclado; foco visível.
- [ ] Contraste AA nas superfícies alteradas.
- [ ] `prefers-reduced-motion` desliga animações.

## 2. QA do worker (ciclo de mineração)

1. `Actions → ai-cron.yml → workflow_dispatch` (ou rodar
   `scripts/worker_cycle.py` local apontando ao staging — ver
   [`PREVIEW_DEPLOYMENT.md`](./PREVIEW_DEPLOYMENT.md) §4).
2. Verificar no job: sites buscados, `entities_processed` por fonte,
   rejeições com motivo, ingest com contadores.
3. Comparar baseline/post das métricas (padrão #048) e registrar.

## 3. Critérios de aprovação de release

- [ ] Suíte verde no commit de release + roteiro §1 completo sem falha grave.
- [ ] Nenhuma regressão de invariante: quórum 3, quarentena ativa,
      sanitização de logs, rate limits.
- [ ] Métricas pós-deploy estáveis por ≥1 ciclo do cron
      ([`MONITORING.md`](./MONITORING.md)).
- [ ] Achados registrados em `SPRINT.md` (mesmo os não bloqueantes).

## 4. Classificação de defeitos

| Severidade | Exemplo neste projeto | Ação |
|---|---|---|
| **S1** | fato sem quórum promovido; segredo em log/resposta | rollback + correção imediata |
| **S2** | ingest quebrado; degradação silenciosa; painel mentindo | correção antes do próximo cron |
| **S3** | motivo de rejeição errado; UI sem fallback visível | correção na sprint |
| **S4** | cosmético | backlog |

## 5. Ferramentas

- Mock server de UI: `python src/frontend/mock_server.py`.
- Verificações CORS auxiliares: `tests/check_cors.py`.
- Auditorias read-only: `scripts/audit_post_clean.py`,
  `scripts/audit_cross_source.py`.
- Estresse de memória: `scripts/stress_episodes.py N`.
