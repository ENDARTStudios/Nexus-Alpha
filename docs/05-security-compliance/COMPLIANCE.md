# ⚖️ Conformidade — Nexus-Alpha

Cobertura: proteção de dados (LGPD/GDPR), ética de mineração web, licenças de
terceiros e conformidade técnica exigida pelos gates de CI.

---

## 1. Proteção de dados (LGPD/GDPR)

### Princípios aplicados
- **Minimização:** o sistema processa conteúdo **público de páginas web**
  e extrai fatos objetivos — não perfis pessoas; nomes de figuras públicas
  aparecem apenas como entidades de fatos publicados (ex.: atletas, cientistas).
- **Finalidade:** construção de grafo de conhecimento público verificado;
  sem marketing, sem publicidade, sem decisão automatizada sobre indivíduos.
- **Segurança:** zero credencial em código; logs sanitizados
  (`log_sanitizer.py`); Space privado; segredos apenas via variáveis de
  ambiente criptografadas (HF) e Repository Secrets (GitHub).
- **Direitos do titular:** não há cadastro de usuários; o chat não exige
  identificação. Mensagens de chat têm histórico volátil curto por
  `session_id` aleatório (sem PII intencional). Remoção: requisito futuro —
  hoje não há dado pessoal coletado do usuário para remover.

### Dados de acesso técnico
- Rate limiter usa IP transiente apenas para throttling (5 req/min), sem
  persistência analítica de identidade.

## 2. Ética e legalidade da mineração

| Prática | Regra |
|---|---|
| `robots.txt` dos sites | respeitado na política de coleta; fontes das seeds curadas são públicas e verificadas manualmente (HTTPS/200) |
| Identidade do coletor | `AntiBlockSystem` rotaciona UA/Referer para **reduzir bloqueio indevido de IPs de nuvem** — não para fraude; conteúdo coletado é público |
| Carga no alvo | delays dinâmicos; 1 ciclo a cada 6h; limites de conexão em `settings.yaml` — sem scraping agressivo |
| Conteúdo extraído | armazenado como **triplas factuais** (afirmações), nunca republicação de texto; atribuição da `source_url` permanece no grafo (`:FonteWeb`) |
| Paywall/login | fora de escopo: o miner não autentica em sites |

> Nota de honestidade: o anti-bloqueio existe porque IPs de datacenter (Actions)
> são bloqueados em massa mesmo para tráfego legítimo. A política interna é
> volume mínimo, conteúdo público, sem burla de autenticação — conforme
> `COMPLIANCE`, qualquer nova fonte passa pela validação manual de seeds (#048).

## 3. Licenças de terceiros

- **MiroFish** (inspiração da simulação de enxame) é **AGPL-3.0**: **nenhum
  código reutilizado** — implementação original apenas com stdlib
  (`src/simulation/`).
- Dependências: `requirements*.txt` — todas permissivas (MIT/BSD/Apache);
  verificar antes de adicionar qualquer dependência AGPL/ GPL ao runtime.
- spaCy modelo `pt_core_news_sm` (CC BY-SA): usado como ferramenta, sem
  incorporação do modelo no repositório.

## 4. Conformidade técnica (gates obrigatórios)

| Gate | Requisito | Falha = merge bloqueado |
|---|---|---|
| Anti-leak | nenhum segredo literal em `src/` | `ai-validation.yml` passo 4 |
| Testes | `pytest -q` verde (~195) | passo 5 |
| Governança | `SPRINT.md` presente na raiz | passo 6 |
| Proxy allowlist | rotas do proxy conforme teste Node | passo 8 |

## 5. Checklist de conformidade para novas features

- [ ] A feature coleta dado pessoal? Se sim: parar e justificar (provavelmente fora de escopo).
- [ ] Nova fonte de dados: URL pública, HTTPS/200, sem login, respeita robots?
- [ ] Nova dependência: licença permissiva? entra em qual `requirements-*`?
- [ ] Toque em dado de usuário: estado onde vive, retenção, como apagar?
- [ ] Logs: passam pelo sanitizador? Nenhum segredo/payload sensível?
