"""#048.6 batch 3 — seeds curadas sobrevivem ao top_k do worker.

Regressão do run 36333813255: `RAGEngine.fetch_and_verify` minera
`queries[:top_k]`; com top_k=40 e clusters no fim da lista, as URLs RSSSF
caíram silenciosamente (44 alvos -> 40 minerados -> RSSSF ausente do log).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.worker_cycle as worker
from src.miner.seed_loader import cluster_to_seeds, load_seed_clusters


def test_merge_urls_puts_clusters_first_without_duplicates():
    base = ["https://a.com/1", "https://b.com/2", "https://a.com/1"]
    cluster = ["https://c.com/3", "https://a.com/1"]
    merged = worker._merge_urls(base, cluster)
    assert merged[0] == "https://c.com/3"
    assert len(merged) == len(set(merged))
    assert set(merged) == {"https://a.com/1", "https://b.com/2", "https://c.com/3"}


def test_top_k_covers_all_curated_seeds_plus_base():
    data = load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")
    seeds = cluster_to_seeds(data)
    # top_k precisa cobrir seeds estáticas + clusters; queries DDG excedentes
    # caem na cauda (descartáveis), nunca as curadas.
    assert worker.WORKER_TOP_K >= len(worker.SEED_QUERIES) + len(seeds), (
        f"WORKER_TOP_K={worker.WORKER_TOP_K} < "
        f"seeds({len(worker.SEED_QUERIES)}) + clusters({len(seeds)})"
    )


def test_rsssf_urls_are_injected_from_manifest():
    data = load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")
    seeds = cluster_to_seeds(data)
    assert "https://www.rsssf.org/sacups/copalib.html" in seeds
    assert "https://www.rsssf.org/tablesb/brazchamp.html" in seeds


def test_merged_list_keeps_rsssf_within_top_k():
    data = load_seed_clusters(ROOT / "config" / "seed_clusters.yaml")
    seeds = cluster_to_seeds(data)
    merged = worker._merge_urls(list(worker.SEED_QUERIES), seeds)
    for url in ("https://www.rsssf.org/sacups/copalib.html",
                "https://www.rsssf.org/tablesb/brazchamp.html"):
        assert url in merged[:worker.WORKER_TOP_K], url
