# 🧪 Testing — Estratégia e Execução (Nexus-Alpha)

Suíte: **pytest**, ~195 testes, 100% verdes é requisito de merge.
Restrição de arquitetura de testes: rodam no **CI lite**
(`requirements-dev.txt` — sem torch, transformers, spacy, sem bancos reais).

```bash
python -m pytest -q              # suíte completa (é o que o CI roda)
python -m pytest tests/ -v       # verboso
python -m pytest tests/test_predicate_mapper.py -v   # arquivo específico
```

---

## 1. Cobertura por camada

| Camada | Arquivos de teste | Notas |
|---|---|---|
| Miner | `test_miner.py`, `test_miner_pipeline.py`, `test_anti_block.py`, `test_quarantine.py`, `test_agent_reach.py`, `test_browser_miner.py`, `test_reach_integration.py`, `test_seed_clusters.py`, `test_domain_reputation.py` | inclui validação estrutural de seeds (HTTPS, domínio proibido, wikipedia-only) |
| Cognition | `test_cognition.py`, `test_nlp_extractor.py`, `test_extractor.py`, `test_predicate_mapper.py`, `test_triple_refiner.py`, `test_canonicalizer.py`, `test_span_validator.py`, `test_extraction_equivalence.py`, `test_entity_resolver.py`, `test_llm_extractor.py`, `test_reasoning_engine.py`, `test_rag*`/`test_graph_rag.py`, `test_chat_service.py`, `test_cross_source_audit*.py`, `test_inspect_cross_lingual_divergence.py` | golden tests determinísticos (ex.: `usa`/`UTILIZA`→`UTILIZA`, `conecta-se a`→`CONECTA_A`) |
| Database/Memory | `test_graph_connector.py`, `test_vector.py`, `test_memory.py`, `test_brain_memory.py`, `test_graph_topology.py`, `test_embeddings.py` | fakes de Neo4j/Qdrant; idempotência `fact_hash+day` |
| Security | `test_triangulation.py`, `test_security_sanitizer.py`, `test_proxy.py`, `test_rate_limiter.py`, `test_quarantine.py` | inclui anti-leak (nenhum segredo em saídas) |
| API/Integração | `test_main.py`, `test_chat_api.py`, `test_ingest_accounting.py` | degradação offline incluída (`demo-memory`) |
| Simulation | `test_simulation.py` | determinismo por seed |
| Training (opt-in) | `test_training_sft.py` | **sem** torch/llamafactory |

## 2. Tipos de teste exigidos

1. **Golden/determinístico** para o refino: par `entrada → saída` fixo
   (padrão #041/#042: `José ≡ Jose`, `zapearia → invalid_predicate`).
2. **Caminho de erro**: cada handler tem teste (quarentena, payload >1MB,
   rate limit, brute-force).
3. **Degradação**: sem Neo4j/Qdrant/spaCy o comportamento é definido e
   testado (`db_status: "demo-memory"`, `source: "volatile"`).
4. **Anti-leak**: nenhum teste imprime/persiste segredo; `test_ingest_accounting.py`
   e `test_seed_clusters.py` carregam o padrão.
5. **Estrutural de config**: seeds/allowlists validadas por teste antes de
   irem a produção.

## 3. Regras para novos testes

- Um arquivo por módulo: `tests/test_<modulo>.py`.
- Sem rede real, sem banco real, sem modelo pesado — fakes/stubs.
- Determinismo: sem `sleep` arbitrário; seeds fixas na simulação.
- pytest-asyncio para corrotinas.
- Novo motivo de rejeição → novo caso de teste com o motivo tipado.

## 4. O que NÃO é testado aqui (e onde testar)

| Gap | Onde cobrir |
|---|---|
| UI real (cliques, visual) | [`QA_TESTING.md`](./QA_TESTING.md) + mock server (`src/frontend/mock_server.py`) |
| Allowlist do proxy | validação Node no CI (passo 8) + `tests/check_cors.py` auxiliar |
| Carga/estresse de memória | `scripts/stress_episodes.py` (fora da suíte; resultado registrado em `SPRINT.md`) |
| Integração real com AuraDB/Qdrant | validação manual em produção ([`MONITORING.md`](./MONITORING.md)) |

## 5. Interpretando falhas comuns

| Falha típica | Causa provável |
|---|---|
| `PYTHONPATH` / import error | rodar da raiz ou `export PYTHONPATH=$(pwd)` |
| Teste de topologia do grafo falha | mudança de schema sem atualizar o teste (ex.: novo campo em `:FonteWeb`) |
| Golden de predicate falha | novo alias colidiu com vocabulário — revisar `EXTRA_MAP` e motivos |
| Anti-leak falha | literal de segredo em teste/payload — substituir por fake |

## 6. DoD de teste (toda PR)

- [ ] Suíte verde local (`pytest -q`).
- [ ] Novo comportamento tem teste; caminho de erro incluído.
- [ ] Nenhuma dependência pesada adicionada à suíte.
- [ ] Números de teste citados no `SPRINT.md` ao fechar a sprint.
