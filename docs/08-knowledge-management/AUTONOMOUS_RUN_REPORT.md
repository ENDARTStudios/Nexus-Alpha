# Relatório Autônomo — Nexus-Alpha

## 1. Estado inicial
- repo HEAD: `e634763` (feat(miner): gazetadoparana para garrincha_botafogo)
- branch: `main`
- Space: saudável (200), metrics 200
- Vercel: 429 rate-limited (BLOCKED_NETWORK)
- métricas pré-F1: facts=183, duplicate_cross_domain=0, verified=0, vectors=785
- backlog: #058.11.2 (F1 concluído), #048.5 (Cenário B - pendente)

## 2. Inventário
- arquivos rastreados: 222
- módulos: src/cognition, src/miner, src/database, src/brain, src/security, src/frontend, scripts/, tests/, config/, .github/workflows/, dashboard/
- não rastreados: .autonomous/, reports/, scripts/*.py (audits/probes), AGENTS.md, .github/agents/autonomo.md

## 3. Segurança
- anti-leak CI-parity: clean (grep `NexusSecurePass2026` sem hits)
- segredos: .env não rastreado, reports/ gitignored, logs sanitizados
- bandit: clean (0 findings high severity)
- pip-audit: BLOCKED_NETWORK (2 tentativas, timeout 25 min — PyPI advisory DB inacessível)
- gitleaks: não instalado (opcional)

## 4. Qualidade
- pytest sistema: **437 passed, 18 skipped** (15.99s)
- pytest venv (spaCy): **453 passed** + 1 falha pré-existente (`test_validator_does_not_import_heavy_training_stack`)
- ruff: 38 errors (dívida pré-existente, CI não roda ruff — fora do gate)
- node policy test: 7 pass, 0 fail
- lint/docs: SPRINT/TASKS atualizados

## 5. Governança
- SPRINT.md atualizado: F1 + Cenário B documentados
- docs/03-development-process/TASKS.md atualizado: #058.11.2 ✅, #048.5 (Cenário B em execução)
- invariantes preservadas: quorum=3, seeds validadas, anti-leak OK, sem treino, sem force-push, staging explícito
- exceções registradas: pip-audit BLOCKED_NETWORK, Vercel 429, ruff dívida

## 6. Backlog executado

| Issue/Tarefa | Status | Commit/PR | Evidência |
|---|---|---|---|
| #058.11.1 F3 (rejeição não-proposicional) | ✅ DONE | `141ffa5` | 414 testes, CI `36199200839` |
| #058.11 re-diagnóstico pós-F3 | ✅ DONE | `2d3c9db` | relatório `extraction_gap_058_11_post_f3.json`, CI `36199913041` |
| #058.11.2 F1 (nominal/copular gateado) | ✅ DONE | `c03b4fd` / `0874948` | dry-run 10/10 gates PASS, `new_triples=16`, `target_fact_hits=4`, CI `36216959187` |
| #058.11.2 doc fix (default True) | ✅ DONE | `0874948` | SPRINT corrigido |
| #048.5 Cenário B (gazeta) | 🟡 PARTIAL | `e634763` | seed alterado, worker `36284673413`, cross-domain não melhorou |
| Auditorias read-only pós-F1 | ✅ DONE | — | `extraction_parity`, `entity_linking`, `cross_source` (2026-09-26) |
| Auditorias read-only pós-seed | ✅ DONE | — | mesmos arquivos com sufixo `_seed_change` |

## 7. Bloqueios

| Bloqueio | Causa | Ação necessária | Continuou? |
|---|---|---|---|
| pip-audit timeout | PyPI advisory DB inacessível | tentar mirror local ou pular em CI | ✅ (marcado, não bloqueia) |
| Vercel 429 | rate limit | aguardar ou usar Space como truth source | ✅ (Space saudável) |
| pip-audit retry 3 | rede externa falha | marcar BLOCKED_NETWORK após 3 tentativas | ✅ (2 tentativas, documentado) |
| ruff 38 errors | dívida pré-existente, CI não exige | opcional: fix incremental em PR futuro | ✅ (não bloqueia) |

## 8. Produção

- **F1 worker** (run `36261835213`): 31/31 ingest, 0 LLM extract, raw=557, canon=208, facts 183→221 (+38), `duplicate_cross_domain` 0→1, `verified` 0, consolidação 200.
- **Seed change worker** (run `36284673413`): gazeta adicionada, 41 URLs, raw=1114, canon=417, facts 221→223 (+2), `duplicate_cross_domain` 1→1 (inalterado), `verified` 0.
- Snapshots: `aura_snapshot_pre_f1_worker.json`, `aura_snapshot_pre_seed_change.json` (3924 nós/3295 rels).
- Baselines: `baseline_pre_f1_worker.json`, `baseline_pre_seed_change.json`.

## 9. Cognição

| Métrica | Pré-F1 | Pós-F1 (worker 1) | Pós-seed (worker 2) |
|---|---|---|---|
| facts | 183 | 221 | 223 |
| canonical_triples (Space) | 0 | 208 | 417 |
| raw_triples (Space) | 0 | 557 | 1114 |
| **duplicate_cross_domain** | **0** | **1** | **1** |
| facts_with_two_or_more_domains | 0 | 1 | 1 |
| verified_facts_domain_independent | 0 | 0 | 0 |
| max_domain_confirmations (graph) | 4 | 5 | 5 |
| quorum=3 atingido? | não | não | não |
| fallback_promoted_to_graph | 0 | 0 | 0 |
| unaccounted_raw | 0 | 0 | 0 |
| canonical_to_fact_gap | 0 | -22 | N/A |
| top_invalid_predicates | [] | [] | [] |

**Fato cross-domain único**: `MANUEL FRANCISCO DOS SANTOS --DEFENDEU--> BOTAFOGO DE FUTEBOL E REGATAS` (pt+en wiki). 
- Gazeta produz mesmo subject+object mas predicado **SER** (single-domain).
- Nenhuma 3ª fonte produz **DEFENDEU** entre fontes HTML estáticas testadas.

**Root causes persistentes** (parity audit):
- `predicate_divergence`: 2 (gazeta SER vs wiki DEFENDEU)
- `extraction_absence`: 2
- `true_content_difference`: 1

## 10. Treino
- gate: `verified_facts_domain_independent = 0 < 10` → **FECHADO**
- não treinado, não exportado dataset, não configurado LlamaFactory
- registro: bloqueio documentado

## 11. Próximos passos recomendados

1. **#048.6 — Escalar para outros clusters curados**  
   Aplicar a mesma validação de seeds + worker em clusters onde há >2 domínios produtivos (ex: `santos_fc` já tem 3 domínios produtivos: pt/en wiki + santosfc.com.br + ge). Medir se `duplicate_cross_domain` sobe em fatos existentes.

2. **#048.5 em outros fatos do cluster Garrincha**  
   Testar se gazeta produz cross-domain em outros fatos do cluster (ex: `Garrincha --JOGOU--> Botafogo`, `Garrincha --VENCEU--> Carioca`). Auditorias de paridade mostram `targets_with_both_canonical=4` — verificar se algum vira cross-domain.

3. **#047.2 / #045.3 — Não prioritários agora**  
   Entity linking: 0 potential_verified_if_medium_aliasing, 5 object_variant. Predicate divergence (SER vs DEFENDEU) é semântica real, não gap de mapeamento.

4. **#055 API Almanaque** — bloqueado legal/paid; não perseguir sem Elite.

5. **Observabilidade**  
   - Adicionar métrica `cross_domain_by_predicate` no Space para rastrear SER vs DEFENDEU separadamente.
   - Pipeline note: SER share controlado (0.359 pós-F1) — monitorar.

6. **Governança**  
   - Adicionar `.autonomous/` ao `.gitignore` (higiene).
   - Commit `AUTONOMOUS_RUN_REPORT.md` + `.autonomous/summary.json` como evidência final.

---

**Conclusão**: F1 (#058.11.2) completo e validado em produção (Cenário B parcial). A extração nominal/copular gateada funcionou — aumentou extração 38 fatos, reduziu SER share, não gerou lixo. O gargalo cross-domain persiste por divergência de predicado (SER vs DEFENDEU) e ausência de 3ª fonte DEFENDEU em HTML estático. Recomendação: escalar validação para clusters com mais domínios produtivos (#048.6).