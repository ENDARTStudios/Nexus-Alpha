# BLOCKED_052_4_SPACE_SYNC

## Problema

A tentativa automática de sincronizar o HF Space para o HEAD atual **não foi permitida**:
o repositório do Space divergiu do histórico do GitHub (não é fast-forward).

## Evidência

- HEAD local: `c0c3160`
- Space sha observado: `85355c6d0e32651eebe4acdf1eb7c7103f6fc245` (`lastModified=2026-09-25T03:03:55Z`)
- Git remoto acessível: **SIM** (`git ls-remote`)
- Backup do Space: **SIM** (sha `85355c6d…`) em `.autonomous/space_sync/` (não commitado)
- Ancestor/fast-forward: **NÃO** (`merge-base --is-ancestor` exit 128)
- Push tentado: **NÃO** (não permitido)
- Push resultado: **N/A**
- Build resultado: **N/A**
- Telemetria após sync: **ainda ausente** (`concept_count`, `fact_count`, `run_scoped_gap`, `graph_scoped_gap`)
- Causa: histórico do Space ≠ histórico do GitHub (Space é snapshot de deploy)

## Ação manual do Operador

1. Abrir o HF Space `ENDARTStudios/Nexus-Alpha`.
2. Do diretório do repo, com `huggingface_hub` instalado e `HF_TOKEN`/`HF_SPACE_URL` definidos:
   ```powershell
   $env:HF_SPACE_URL="https://huggingface.co/spaces/endartstudios/nexus-alpha"
   python scripts/deploy_hf_space.py
   ```
   (ou, no painel do Space, **Factory Reboot / Restart** após garantir o upload do código atual).
3. Aguardar build verde.
4. Validar `/api/metrics` esperando:
   - `concept_count`, `fact_count`
   - `ingestion_accounting.run_scoped_gap`, `ingestion_accounting.graph_scoped_gap`
   - `verification.quorum = 3`, `fallback_promoted_to_graph = 0`, `top_invalid_predicates = []`, `unaccounted_raw = 0`
5. Depois executar o **#048.10H** real.

## Segurança

- Nenhum worker executado; nenhuma escrita em Neo4j/Qdrant; nenhum treino.
- Nenhum force-push (GitHub ou Space).
- O backup do Space foi registrado em `.autonomous/space_sync/`, **não commitado**.
