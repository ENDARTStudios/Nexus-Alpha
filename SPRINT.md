# 🏁 Sprint Governance & Backlog Log — Nexus-Alpha

Este documento estabelece o escopo de execução exclusivo para a **Sprint Atual**.
Nenhum agente, modelo de IA ou desenvolvedor pode realizar alterações em arquivos
ou introduzir dependências que não estejam explicitamente mapeadas neste documento.

---

## 📅 Sprint Atual: `v1.2.0-alpha` — Ajuste de Rotas e Conexão de Produção

- **Status:** 🟢 Planejada / Pronta para Execução
- **Impacto:** Crítico (Ativação do banco de dados Neo4j real em produção e correção do endpoint de healthcheck)
- **Complexidade:** Baixa (Configuração de middlewares e strings de conexão no Hugging Face)

---

## 🎯 Funcionalidade Alvo e Escopo

Resolver o isolamento de rede do contêiner no Hugging Face Space para que ele consiga
se autenticar no Neo4j AuraDB e ajustar as rotas do FastAPI para responder corretamente
ao ping de monitoramento.

### 📋 Tarefas Mapeadas (Mapeamento de GitHub Issues)

#### [Issue #016] — Correção do Endpoint `/health` e Rotas do FastAPI

- **Descrição:** Adicionar explicitamente a rota `@app.get("/health")` no arquivo
  `app.py` do Hugging Face. O roteador atual está operando apenas na raiz `/`, fazendo
  com que o monitor do Space retorne 404 ao buscar o healthcheck estruturado.
- **Critérios de Conclusão:**
  - Chamadas para `GET /health` devem retornar `200 {"status": "ok"}` no contêiner de produção.
- **Arquivos Afetados:**
  - `app.py` (Modificação)

#### [Issue #017] — Depuração do Driver de Conexão Bolt (Neo4j AuraDB)

- **Descrição:** Ajustar o protocolo do driver no `graph_connector.py` para usar
  `neo4j+s://` (exigido pelo AuraDB para criptografia TLS estrita em nuvem) em vez de
  `bolt://` simples, resolvendo o fallback automático para `demo-memory`.
- **Critérios de Conclusão:**
  - O log do Space deve exibir `Conexão assíncrona com o Neo4j estabelecida com sucesso`
    apontando para o cluster real.
- **Arquivos Afetados:**
  - `src/database/graph_connector.py` (Modificação)

---

## 🛡️ Restrições de Deploy e Critérios de Aceitação (Definition of Done)

1. **Pass de Testes:** O validador do GitHub Actions (`ai-validation.yml`) deve dar sinal verde.
2. **Conexão Real:** O próximo disparo manual do worker deve retornar `db_status: cluster-active`
   e gravar as 40 tripletas diretamente no grafo online.
