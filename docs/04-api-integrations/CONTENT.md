# 📰 Conteúdo — Política de Coleta e Qualidade Semântica (Nexus-Alpha)

O "conteúdo" do Nexus-Alpha é matéria-prima factual: páginas públicas
transformadas em triplas verificadas. Este doc define **o que entra**, **de
onde** e **com que qualidade mínima**.

---

## 1. Domínios de interesse

- **Domínio atual (sprint #048):** futebol brasileiro — Santos FC, Estádio
  Urbano Caldeira (Vila Belmiro), Pelé, Garrincha/Botafogo.
- Expansão para novos domínios replica o modelo de clusters curados
  (ver §3).

## 2. Fontes (seeds)

1. **Seeds base do worker** (`scripts/worker_cycle.py`) — malha inicial.
2. **Clusters curados** (`config/seed_clusters.yaml`, #048): 4 clusters,
   cada um com **≥3 domínios**, **≥2 publishers** e **≥1 publisher fora de
   Wikipedia**. Publicadores validados manualmente (HTTPS/200/texto):
   `pt.wikipedia.org`, `en.wikipedia.org`, `santosfc.com.br`,
   `ge.globo.com`, `botafogo.com.br`.
3. **Almanaque (futuro, #055):** API REST estruturada como fonte primária —
   candidatos descartados na validação #048: `almanaquedosclubes.com` (404),
   `cbf.com.br` (ConnectError).

### Regras de admissão de fonte nova
- [ ] URL pública, HTTPS 200, sem login/paywall.
- [ ] Não está em `low_trust_patterns` (reddit, medium, wordpress,
      blogspot, tumblr, substack — score 0.4).
- [ ] Reputation adequada: `.org`/`.edu`/`.gov` = 0.9; publisher da
      allowlist `REPUTABLE_PUBLISHERS` = 0.85; desconhecido `.com` = 0.6
      (**vai para quarentena** — limiar 0.70).
- [ ] Conteúdo **declarativo** (páginas JS/listing rendem
      `entities_processed: 0` — lição #048).
- [ ] Adição só no `seed_clusters.yaml` com validação estrutural do teste
      (`tests/test_seed_clusters.py`: HTTPS, domínio proibido,
      wikipedia-only, duplicatas).

## 3. Ciclo de vida do conteúdo

```text
Página pública → limpeza de ruído (nav/footer/ads; mínimo 200 bytes de texto)
  → triplas {sujeito, predicado, objeto} (spaCy PT / heurístico)
  → refino determinístico (canonicalizer → predicate mapper → span validator)
  → ingest autenticado
     ├─ passa + quórum 3 domínios → :Fato verificado
     ├─ passa sem quórum → aguarda corroboração
     └─ rejeitado → quarentena (motivo tipado, nunca promovida)
```

## 4. Padrões de qualidade (o que é aceito)

1. **Sujeito/objeto são entidades**, não fragmentos: data (`EM 1959`),
   oração (`COM ISSO`), locução (`APOS A PUBLICACAO EM 1986`) são rejeitados
   pelo span validator (#050).
2. **Predicado do vocabulário controlado** (≤30, caixa alta): UTILIZA,
   POSSUIR, PRODUZ, CONTIENE, CONECTA_A, DEFINE, APRENDE…; verbos novos só
   via #044 (aliases de alta confiança, com teste por par `raw → canonical`).
3. **Normalização canônica:** `José ≡ Jose`, `A IA ≡ IA`,
   `conecta-se a → CONECTA_A` (fold NFKD + artigos + hífen — #041).
4. **Independência real:** mesmo fato de PT e EN da Wikipedia **não**
   corrobora (superfícies semânticas distintas — gargalo R1) e hosts do
   mesmo publisher ainda contam separado (dívida #053).

## 5. Idiomas

- Extração configurada para **pt-BR** (spaCy `pt_core_news_sm`); conteúdo EN
  é aceito mas hoje gera superfícies distintas (problema de research R1 —
  não "consertar" baixando quórum ou promovendo por embedding).

## 6. Conteúdo sensível / proibições

- Sem mineração de conteúdo atrás de login/paywall.
- Sem fontes sensacionaisistas: `security_policies.json` penaliza
  densidade de clickbait (pt/en) com `confidence_penalty: 0.5`.
- Sem dado pessoal de não-figuras-públicas; sem republicação de texto
  (só fatos estruturados com `source_url` preservada em `:FonteWeb`).

## 7. Indicadores de qualidade de conteúdo

| Indicador | Sinal saudável |
|---|---|
| `entities_processed` por fonte | > 0 em páginas declarativas |
| `rejection_reasons` dominante | `unmapped_predicate` de verbos legítimos (não lixo) |
| `top_invalid_predicates` | vazio |
| `ingestion_accounting.duplicate_cross_domain` | > 0 (meta) |
| Cobertura de domínio | clusters com todos os domínios acessíveis (validar seeds a cada sprint) |
