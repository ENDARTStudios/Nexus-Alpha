# 🔐 Security Review — Processo e Checklist (Nexus-Alpha)

Modelo de ameaças resumido e o processo obrigatório de revisão de segurança.
Política viva em `config/security_policies.json`; gates automáticos em
`.github/workflows/ai-validation.yml`.

---

## 1. Modelo de ameaças (resumo)

| Ameaça | Vetor | Defesa em profundidade |
|---|---|---|
| Vazamento de segredo | código/logs/CI públicos | zero-trust (`os.environ.get`), `log_sanitizer.py` → `[MASKED]`, gate anti-leak (grep) |
| Ingest malicioso | `POST /api/ingest` | `X-Nexus-Token` + Bearer HF; `interceptor.py` (>1MB, brute-force 10); Space privado |
| Abuso do chat | `POST /api/chat` | rate limit 5 req/min/IP (429); respostas extrativas (sem execução de LLM arbitrário) |
| Desinformação | conteúdo minerado | `TriangulationFilter` (quórum 3 **domínios**), reputação de domínio, quarentena, sensationalism penalty |
| Enumeração de rotas | superfície Vercel | `vercel.json` + `robots.txt` bloqueando `/api/`, `/_next/image*`; allowlist do proxy testada no CI |
| CORS permissivo | origens arbitrárias | `NEXUS_CORS_ORIGINS`/`NEXUS_CORS_ORIGIN_REGEX` (default: vercel.app) |
| Segredo no frontend | env do cliente | proibição de `NEXT_PUBLIC_` para segredos; proxy server-side injeta credenciais |

## 2. Gates automáticos (todo push/PR)

1. **Anti-leak grep:** `grep -rni "NexusSecurePass2026" src/ --exclude="graph_connector.py"` — match quebra o build.
2. **Suíte completa** (inclui testes de sanitização/quarentena/limites).
3. **Allowlist do proxy** validada em Node.
4. `SPRINT.md` presente (governança).

> O grep é intencionalmente simples e auditável; scanners adicionais (ex.:
> **Strix**, opt-in via `scripts/security_audit.py`) são complemento manual,
> nunca substituto.

## 3. Checklist de security review (toda PR sensível)

Aplica-se a: auth, endpoints, ingest, proxy, logging, dependências, config.

- [ ] Nenhuma credencial literal; nada sensível com `NEXT_PUBLIC_`.
- [ ] Logs passam pelo sanitizador; nenhuma mensagem nova com payload cru.
- [ ] Todo endpoint novo exige autenticação equivalente aos existentes.
- [ ] Limites respeitados: payload ≤1MB, rate limits, brute-force.
- [ ] Entrada do usuário nunca vira Cypher/SQL concatenado (parâmetros `$`).
- [ ] Dependência nova: licença ok, entra no `requirements-*` correto,
      justificada ([`INTEGRATIONS.md`](./INTEGRATIONS.md) §7).
- [ ] Config de segurança (`security_policies.json`, allowlists) alterada
      **com** teste.
- [ ] Degradação não abre bypass (ex.: fallback in-memory não aceita ingest
      sem auth).

## 4. Procedimento de incidente (segredo exposto)

1. **Rotacionar** imediatamente: `NEXUS_API_TOKEN`, `HF_TOKEN`,
   `NEO4J_PASSWORD`, `QDRANT_API_KEY` (Space + Repository Secrets + `.env`).
2. Auditar alcance: `git log -S "<segredo>"`, logs do Actions/Space.
3. Remover a exposição em commit novo (**sem** force-push).
4. Registrar apêndice em `SPRINT.md` (o quê, quando, rotação feita).
5. Runbook completo: [`BACKUP_DR.md`](./BACKUP_DR.md) DR-4.

## 5. Revisões periódicas

| Cadência | Atividade |
|---|---|
| Por PR | checklist §3 quando sensível |
| Por sprint | revisar allowlists (`REPUTABLE_PUBLISHERS`, seeds) e `security_policies.json` contra mudanças de fontes |
| Por ciclo (6h) | gate automático + `/api/metrics` (quarentena, rejeições) |
| Oportunista | `scripts/security_audit.py` (Strix, opt-in) para pentest autônomo |

## 6. Contatos e responsabilidade

Projeto mantido por ENDARTStudios (repositório privado). Toda decisão de
segurança duradoura vira ADR ([`ADR.md`](./ADR.md) — ADR-002, ADR-007,
ADR-011) e regra em [`RULES.md`](./RULES.md) §2.
