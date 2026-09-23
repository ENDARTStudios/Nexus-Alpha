# ✍️ Style Guide — Código e Commits (Nexus-Alpha)

O guia de design visual está em [`DESIGN.md`](./DESIGN.md); este cobre **código**.

---

## 1. Python (runtime `src/`, `app.py`, `scripts/`)

### Geral
- Python 3.10+; **assíncrono por padrão** (httpx, asyncio) — proibida
  biblioteca síncrona de bloqueio no caminho de I/O (regra de ouro do projeto).
- Type hints em funções públicas; `pydantic` para modelos de payload.
- Sem segredo literal: acesso exclusivo via `os.environ.get()`.
- Docstrings curtas em módulos públicos; comentários só para **restrições que
  o código não mostra** (ex.: por que sem APOC, por que quórum 3).

### Convenções do repositório
- Nomes de arquivo em `snake_case.py`; classes em `CamelCase`.
- Módulos por camada (`src/miner`, `src/cognition`, `src/database`,
  `src/security`, `src/brain`, `src/simulation`, `src/training`) — nada de
  código de uma camada invadir outra (ver [`ARCHITECTURE.md`](./ARCHITECTURE.md) §1).
- Cypher: **puro, sem APOC**, chaves em caixa alta para predicados
  (`:RELACIONA {predicate: "UTILIZA"}`), labels `:Conceito`, `:Fato`,
  `:Episodio`, `:FonteWeb`.
- Configuração em `config/settings.yaml` / `security_policies.json` —
  números mágicos viram config com comentário do limiar.

### Determinismo (crítico nesta codebase)
- Funções de refino (canonicalizer, predicate_mapper, span_validator) são
  **puras**: mesma entrada → mesma saída, sem I/O, sem LLM, sem rede.
- Motivos de rejeição são strings tipadas em inglês minúsculo
  (`unmapped_predicate`) — o contador de métricas é dinâmico.

### Testes
- Um arquivo `tests/test_<modulo>.py` por módulo; sem Neo4j/Qdrant reais
  (fakes); sem torch/transformers/spacy (CI lite).
- Testes de caminho de erro obrigatórios (ver [`ERROR_HANDLING.md`](./ERROR_HANDLING.md) §6).

## 2. TypeScript/React (`src/frontend/`, `src/app/`)

- Next.js 14 App Router; componentes funcionais + hooks; sem classe.
- **Todo fetch passa por `src/frontend/lib/api.ts`/`nexus.ts`/`brain.ts`** —
  nenhum `fetch` direto em componente.
- Cores/tokens conforme [`DESIGN.md`](./DESIGN.md); sem hex avulso fora dos tokens.
- Movimento centralizado em `lib/motion.config.ts`.
- Componentes de dados (BrainPanel) são **read-only**.
- Acessibilidade: checklist em [`ACCESSIBILITY.md`](./ACCESSIBILITY.md) obrigatório.

## 3. Commits

Formato: `tipo(escopo): resumo no imperativo`

```
feat(miner): add curated cross-domain seed clusters for football facts
fix(cognition): guard nonverbal predicates in EntityExtractor
docs(sprint): record #048 production result and root cause
```

- Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.
- Escopos usuais: `miner`, `cognition`, `database`, `security`, `brain`,
  `simulation`, `training`, `frontend`, `observability`, `sprint`.
- **1 item por commit**; staging explícito:

```bash
git status
git add <paths específicos>
git diff --cached
git commit
```

Proibido `git add -A` sem inspeção (histórico: exceções `2a41622`, `712724d`).

## 4. Documentação

- pt-BR; tabelas para limites/valores; evidência numérica quando existir.
- PR que muda comportamento atualiza o doc correspondente em `docs/`.
- Decisões duradouras → ADR em [`ADR.md`](./ADR.md).

## 5. Proibições rápidas (cheat sheet)

| ❌ Nunca | ✅ Sempre |
|---|---|
| Segredo em código/testes/payload | `os.environ.get()` + secrets do CI |
| `git add -A` | staging explícito + `git diff --cached` |
| APOC no Cypher | Cypher puro |
| Baixar quórum/embedding-promotor | quórum 3; embedding só sugere |
| torch/spacy em teste do CI | suíte lite (`requirements-dev.txt`) |
| sync blocking no I/O | httpx/asyncio |
| hex novo no frontend | tokens de [`DESIGN.md`](./DESIGN.md) |
