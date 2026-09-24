# 🚨 Tratamento de Erros — Nexus-Alpha

Princípio central: **degradar graciosamente, nunca descartar conhecimento,
nunca vazar segredo**. Um erro no Neo4j não pode derrubar o Space; um fato
sem quórum vai para quarentena, não para o lixo.

---

## 1. Matriz de degradação (comportamento canônico)

| Falha | Comportamento | Sinal observável |
|---|---|---|
| Neo4j indisponível | ingest não grava; status `failed` (default) ou `degraded`/`partial_success` se `NEXUS_ALLOW_DEMO_FALLBACK=true` | `db_status: "demo-memory"` na resposta; nunca `partial_success` com `entities=0` (#058.4) |
| Qdrant indisponível | vetores em memória (in-process) | `vector_connector` em modo fallback |
| `/api/brain/episodes` sem grafo | leitura da memória volátil | `source: "volatile"` |
| spaCy ausente/falhou | extração heurística (`extractor.py`) | worker segue; CI roda sem spaCy |
| LLM não configurado | chat responde **extrativo** (fatos do grafo) | sem erro, comportamento padrão |
| Modelo spaCy falha no download | `continue-on-error` no cron; fallback no código | logs do Actions |
| Página minerada bloqueia/404 | registrada e pulada; seeds validadas manualmente (#048 descartou 404/ConnectError) | logs do worker |

## 2. Erros de domínio → quarentena, nunca descarte

Triplas rejeitadas pelo refino determinístico recebem **motivo tipado**:

```
ok · missing_entity · unmapped_predicate · invalid_predicate ·
numeric_predicate · url_or_code_predicate · stopword_predicate ·
nonverbal_predicate · modal_predicate · ambiguous_predicate ·
self_loop · span_validator.* (object_date_like, object_prepositional_phrase, ...)
```

- Destino: `RejectionQuarantine` **volátil** (`/tmp`), limite 10k com rotação,
  **nunca promovida ao grafo**.
- Observabilidade: `extraction_quality.rejection_reasons`,
  `top_unmapped_predicates`, `top_invalid_predicates`, bloco `quarantine` em
  `/api/metrics`.
- Fatos com quórum insuficiente: quarentena de triangulação
  (`auto_quarantine_threshold: 0.5` em `settings.yaml`).

## 3. Camada HTTP (`app.py`)

1. **Autenticação:** `POST /api/ingest` exige `X-Nexus-Token` + Bearer HF —
   credencial inválida → 401/403, sem detalhes internos na mensagem.
2. **Payload:** `interceptor.py` rejeita > 1MB (413) e bloqueia brute-force
   após 10 tentativas (429/403).
3. **Rate limit:** `/api/chat` 5 req/min por IP → 429 com mensagem amigável.
4. **Regra de mensagem:** erro retornado ao cliente é curto e em pt-BR;
   stack trace e credenciais **nunca** saem na resposta (logs passam pelo
   `log_sanitizer.py` → `[MASKED]`).

## 4. Frontend

1. Falha de rede no chat → mensagem "Não foi possível falar com a Nexus.
   Tente novamente." + botão de retry; sem travar o widget.
2. Painéis exibem estado do backend (`db_status`, `source`) — fallback é
   **visível** ao operador, nunca silencioso.
3. Nenhum stack trace renderizado no UI.

## 5. Worker (GitHub Actions)

1. Falha de um site não aborta o ciclo: erros são agregados no log do job.
2. Ingest falho → payload não é perdido silenciosamente: o job falha
   (vermelho) para revisão — conhecimento não entra pela metade.
3. `python scripts/train_lora.py train` sem LlamaFactory → erro **amigável**
   (sem traceback cru) — padrão exigido pelo DoD v1.14.

## 6. Regras para escrever tratamento de erros novo

1. Pergunte primeiro: **esse erro pode vazar segredo?** → sanitize.
2. **Esse erro pode perder dado?** → quarentena/queda para fallback durável.
3. **Esse erro pode derrubar o app inteiro?** → isole no módulo; degradação
   graciosa é obrigatória ([`RULES.md`](./RULES.md) §4.5).
4. Erros novos ganham motivo tipado + contadores em `/api/metrics`
   (o contador de `rejection_reasons` é dinâmico — novos motivos não exigem
   mudança em `app.py`).
5. Teste o caminho de erro, não só o feliz (padrão da suíte: testes de
   degradação offline incluídos).
