# SPRINT.md — Nexus-Alpha

## Funcionalidade Alvo (Foco absoluto: maior impacto / menor complexidade)
Formalizar a governança de desenvolvimento, implementar a casca de UI/UX de monitoramento (Next.js + Tailwind + Motion) e blindar o ecossistema contra vazamento de segredos e falhas em produção, sem alterar o core de scraping/NER/grafos.

## Tarefas e Arquivos Afetados (mapadas a Issues hipotéticas)
| Issue | Tarefa | Arquivos Affected | Critério de Conclusão |
|---|---|---|---|
| #101 | Estabelecimento do fluxo de sprint | `SPRINT.md`, `.github/workflows/ai-validation.yml` | Documento preenchido; CI atualizado |
| #102 | Casca de UI Next.js + Tailwind + Motion | `src/frontend/next.config.js`, `src/frontend/app/page.tsx`, `src/frontend/app/layout.tsx`, `src/frontend/components/*.tsx` | 3 telas renderizam sem overflow em 375/390/768px |
| #103 | Skeleton loading + lazy graph + spring animations | `src/frontend/components/MetricCard.tsx`, `src/frontend/components/GraphCanvas.tsx`, `src/frontend/lib/motion.config.ts` | Skeleton visível <300ms; animação spring aplicada |
| #104 | Auditoria de segurança — secrets | `src/main.py`, `app.py`, `src/security/log_sanitizer.py` | Nenhum `.get()` sem `os.environ`; log sanitiza tokens |
| #105 | Sanitização de logs + interceptador de payload | `src/security/log_sanitizer.py`, `src/security/interceptor.py` | Erros de API/DB não expõem chaves/URLs; payload >1MB bloqueado |

## Critérios de Conclusão
- Nenhuma chave/API/token aparece direto no código fonte (apenas `os.environ.get()` com fallback seguro).
- Painel de auditoria responsivo: 375px / 390px / 768px sem overflow horizontal.
- Logs públicos passam pelo sanitizador (`log_sanitizer.py`) antes de escrita.
- Interceptor rejeita JSON >1MB (`interceptor.py`).
- `SPRINT.md` atualizado ao finalizar.

## Plano de Teste
- `tests/test_responsive.py`: verifica dimensões 375/390/768 via Playwright/selenium headless (se disponível) ou assertions de CSS médio.
- `tests/test_security_sanitizer.py`: assert que strings contendo `sk-`, `Bearer`, `bolt://`, `neo4j-password` são removidas de logs simulados.
- `tests/test_interceptor.py`: assert payload 2MB retorna 413; payload 100KB passa.
- `tests/test_ui_motion.py`: assert componentes exportam animações `spring` via `framer-motion`.
