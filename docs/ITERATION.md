# 🔁 Iteration — Ciclo de Sprint e Melhoria Contínua (Nexus-Alpha)

O Nexus-Alpha evolui em **sprints curtas governadas** (não em sprints
calendário): cada ciclo tem um único tema, evidência e DoD. `SPRINT.md` é o
registro vivo; este doc é o manual do ciclo.

---

## 1. Anatomia de um ciclo

```text
1. MEDIR      auditoria read-only + /api/metrics → evidência numérica
2. ESCOLHER   uma alavanca (a maior, com a evidência mais limpa)
3. CONGELAR   SPRINT.md: escopo, arquivos, critérios, fora-de-escopo
4. EXECUTAR   1 issue = 1 commit; suíte verde; docs atualizadas
5. VALIDAR    worker manual (baseline/post) + QA funcional
6. REGISTRAR  resultado real em SPRINT.md; CHANGELOG; ADR se duradouro
7. RETRO      o que a métrica disse? próxima alavanca
```

## 2. Regras do ciclo

1. **Um tema por sprint.** (v1.13.0 = qualidade semântica; v1.12.0-beta =
   memória durável.)
2. **Freeze explícito:** quando o tema pede estabilidade, congela-se
   infraestrutura por N ciclos (v1.13.0: 2–3 ciclos/12–18h de produção) —
   nenhuma mudança de código até a observabilidade confirmar estabilidade.
3. **Opt-in é aditivo:** exceções ao freeze (como v1.14.0/LlamaFactory) são
   100% aditivas, fora do runtime e do CI, e não removem itens do backlog.
4. **Métrica honesta > métrica bonita:** queda por correção de medida
   (#049) é progresso; registrar a redefinição.
5. **Exceções de governança são registradas, não varridas** (commits
   `2a41622`, `712724d` — mantidos, regra reafirmada).

## 3. Fontes de alavanca (o que alimenta a próxima sprint)

| Fonte | Exemplo real |
|---|---|
| Auditoria read-only | #046 → descobriu objetos-fragmento → #050 |
| Gap de contabilidade | #051 gap 12 → #052 observabilidade |
| Resultado de produção | #048 cross_domain=0 → ADR-010 (gargalo semântico) |
| Dívida registrada | #053/#054/#055 |
| Métrica recorrente | `top_unmapped` → #044 |

## 4. Retro — perguntas padrão (fim de cada ciclo)

1. A métrica-alvo se moveu? Se não, a hipótese estava errada ou a medida
   estava errada?
2. Alguma invariante foi pressionada (quórum, determinismo)? Por quê?
3. O que virou dívida nova? Registrou (#NNN)?
4. A documentação de `docs/` ainda é verdadeira?
5. O custo continua zero (nenhum limite de free tier estourando)?

## 5. Critérios para encerrar uma sprint

- [ ] Resultado real (números) registrado em `SPRINT.md`.
- [ ] DoD de cada issue atendido (testes, diff vazio nos arquivos protegidos).
- [ ] `docs/` coerente (CHANGELOG, TASKS, ANALYTICS quando aplicável).
- [ ] Próxima alavanca identificada com evidência — ou freeze justificado.

## 6. Cadência de manutenção contínua (fora da sprint)

| Frequência | Atividade |
|---|---|
| 6h | cron do worker (auto) |
| Semanal | backup (auto) + checagem de monitoramento ([`MONITORING.md`](./MONITORING.md)) |
| Por sprint | revisão de allowlists/seeds; retro |
| Por release | QA funcional ([`QA_TESTING.md`](./QA_TESTING.md)) |

## 7. Lições já institucionalizadas

1. Medir antes de otimizar (seqüência #046→#050→#056→#048).
2. Choke point único de transformação (ingest) facilita cada iteração.
3. Anti-inflação (MERGE `fact_hash+day`) evita retrabalho de dados.
4. Deploy do Space usa a árvore de disco — staging limpo antes de publicar.
5. Métrica flat pós-release não invalida código quando há fragmentação
   histórica — re-ingest controlado é o protocolo.
