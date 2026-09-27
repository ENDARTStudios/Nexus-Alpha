# 📜 Regras — Nexus-Alpha (invioláveis)

Estas regras valem para **qualquer** agente de IA, modelo ou desenvolvedor.
Elas derivam da governança de `SPRINT.md`, dos gateways de CI
(`.github/workflows/ai-validation.yml`) e das decisões registradas em
[`ADR.md`](./ADR.md). Violar qualquer regra desta página bloqueia o merge.

---

## 1. Governança de escopo

1. **`SPRINT.md` é a lei da sprint.** Nenhuma alteração de arquivo ou
   dependência fora do escopo mapeado nela é permitida.
2. **1 item por commit.** Staging explícito (`git add <paths>`, depois
   `git diff --cached`). **Proibido `git add -A` sem inspeção prévia.**
   (Exceções históricas `2a41622` e `712724d` foram mantidas, mas a regra
   voltou a valer a partir delas.)
3. **Sem force-push** em `main`; histórico é imutável — erros se corrigem
   com commits novos.
4. Arquivos de governança obrigatórios: `SPRINT.md` na raiz (validado pelo
   passo 6 do gate de CI).
5. `requirements-dev.txt` e `.github/workflows/` só mudam se a sprint
   mapear explicitamente (o DoD de v1.13/v1.14 exige `git diff --` vazio neles).

## 2. Segurança (zero-trust)

1. **Zero credencial literal.** Segredos só via `os.environ.get()`.
   Repository Secrets no Actions; variáveis criptografadas no Space.
2. **Anti-leak:** o gate faz `grep -rni "NexusSecurePass2026" src/`
   (exceto `graph_connector.py`) e falha o build em caso de match.
   Nunca escreva segredos em código, testes, payloads ou docs.
3. **Sanitização de logs:** toda saída pública passa por `log_sanitizer.py`
   (mascara `bolt://neo4j:...`, tokens `X-Nexus-Token`, `api_key` → `[MASKED]`).
4. **Interceptor:** payloads > 1MB são rejeitados; brute-force bloqueado
   após 10 tentativas.
5. **Space privado:** o frontend fala com o core apenas via proxy Vercel
   server-side (`/api/nexus/[...path]`). Nunca expor `NEXUS_SPACE_URL` com
   prefixo `NEXT_PUBLIC_`.
6. `robots.txt` + `vercel.json` bloqueiam rotas sensíveis (`/api/`, `/_next/image*`).

## 3. Integridade do conhecimento (regras de ouro)

1. **Quórum de triangulação = 3 fontes de domínios distintos.** Proibido
   baixar o quórum para "destravar" métricas.
2. **Independência = domínio (host)** desde #049 — `count(DISTINCT ff.domain)`.
   4 URLs do mesmo domínio valem 1.
3. **Embedding nunca promove fato** — apenas sugere (entity linking é
   diagnóstico até decisão contrária em ADR).
4. **Sem LLM nas etapas determinísticas** de refinamento (canonicalizer,
   predicate_mapper, span_validator). Determinismo é testável; LLM não.
5. **Fato sem quórum vai para quarentena, nunca é descartado.**
6. **Nada toca o Neo4j sem passar** por `SecurityProtocol`
   (domain_score + triangulação) e `refine_triple`.

## 4. Qualidade de código

1. **Todo push em `main`/`dev` e todo PR para `main`** roda a suíte
   (`python -m pytest -q`) — deve permanecer verde (atualmente ~195 testes).
2. Testes novos **não podem depender** de torch/transformers/spacy
   (o CI é lite: `requirements-dev.txt`).
3. Python assíncrono (httpx/asyncio) — proibido introduzir bibliotecas
   síncronas de bloqueio no caminho de I/O.
4. Cypher **puro, sem APOC** (portabilidade AuraDB Free).
5. Degradação graciosa obrigatória: nenhum módulo pode derrubar o app se
   Neo4j/Qdrant/spaCy/LLM estiverem ausentes.

## 5. Fine-tuning (opt-in)

1. LlamaFactory **não** entra no runtime nem no CI; treino é externo (Kaggle).
2. Dataset só com fatos **verificados**; gate de treino: `records >= 50`,
   `verified_facts >= 10`, sem segredos, YAML válido.
3. `scripts/train_lora.py train` sem LlamaFactory instalado deve retornar
   erro amigável (sem traceback cru).

## 6. Documentação

1. PR que muda comportamento documentado atualiza o doc correspondente em
   `docs/` na mesma PR.
2. Resultados de sprint (métricas, causa raiz, decisões) são registrados em
   `SPRINT.md` — que é apêndice, não reescrita.
3. Toda decisão arquitetural duradoura ganha um ADR em [`ADR.md`](./ADR.md).

## 7. Fluxo de commit padrão

```bash
git status                        # inspecione
git add <paths específicos>       # staging explícito
git diff --cached                 # revise o que vai sair
git commit                        # 1 item, mensagem convencional
```
