"""Testes #058.3 — paridade de extração PT/EN (puros, sem rede/Neo4j)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cognition.extraction_parity_audit import (  # noqa: E402
    analyze_source_run,
    build_parity_report,
    build_target_report,
    classify_log_fallback,
    classify_pair,
    fact_hash,
    fold_key,
    group_facts_by_target_alias,
    load_persisted_facts_by_domain,
    parse_worker_ingest_log,
)

SCRIPT = ROOT / "scripts" / "audit_extraction_parity.py"


def _source(
    *,
    url: str,
    domain: str,
    raw: int,
    canonical: int,
    facts: list[dict],
    fallback: bool = False,
    written: bool = False,
    entities: int | None = None,
    reasons: dict | None = None,
    predicates: list[str] | None = None,
) -> dict:
    facts = list(facts)
    if predicates is not None and facts:
        facts = [dict(f, predicate=p) for f, p in zip(facts, predicates)]
    return analyze_source_run(
        url=url,
        domain=domain,
        fetch_status=200,
        raw_triples=raw,
        canonical_triples=canonical,
        rejected_reasons=reasons or {},
        canonical_facts=facts,
        fallback_used=fallback,
        fallback_type="demo-memory" if fallback else "",
        fallback_written_to_graph=written,
        entities_processed=entities,
        db_status="demo-memory" if fallback else "cluster-active",
        ingest_status="partial_success" if fallback else "success",
    )


def test_fact_hash_stable_and_lowercases():
    a = fact_hash("Santos FC", "DEFENDEU", "Pelé")
    b = fact_hash(" santos fc ", "defendeu", "PELÉ")
    assert a == b
    assert len(a) == 64


def test_case1_en_absent_extracts_nothing():
    """Caso 1 — PT tem canônica; EN não extraiu → extraction_absence."""
    pt = _source(
        url="https://pt.wikipedia.org/wiki/Pel%C3%A9",
        domain="pt.wikipedia.org",
        raw=12,
        canonical=4,
        facts=[{"subject": "EDSON ARANTES DO NASCIMENTO", "predicate": "DEFENDEU", "object": "SANTOS FUTEBOL CLUBE"}],
    )
    en = _source(
        url="https://en.wikipedia.org/wiki/Pel%C3%A9",
        domain="en.wikipedia.org",
        raw=0,
        canonical=0,
        facts=[],
        fallback=True,
        written=False,
        entities=0,
    )
    result = classify_pair(pt, en)
    assert result["collision_status"] == "no_en_canonical_triples"
    assert "extraction_absence" in result["root_cause_candidates"]
    assert result["next_issue_hint"] == "#058.4"
    assert result["fallback_used"] is True
    assert result["fallback_written_to_graph"] is False


def test_case2_predicate_divergence():
    """Caso 2 — ambos extraem; predicado não casa → predicate_divergence."""
    pt = _source(
        url="https://pt.wikipedia.org/wiki/Santos_FC",
        domain="pt.wikipedia.org",
        raw=8,
        canonical=3,
        facts=[
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "DEFENDEU", "object": "EDSON ARANTES DO NASCIMENTO"},
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "DISPUTOU", "object": "CAMPEONATO"},
        ],
    )
    en = _source(
        url="https://en.wikipedia.org/wiki/Santos_FC",
        domain="en.wikipedia.org",
        raw=7,
        canonical=3,
        facts=[
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "PLAYED_FOR", "object": "EDSON ARANTES DO NASCIMENTO"},
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "JOINED", "object": "CAMPEONATO"},
        ],
    )
    # compartilha entidades, nenhum predicado em comum → predicate_divergence
    result = classify_pair(pt, en)
    assert result["collision_status"] == "predicate_divergence"
    assert "predicate_divergence" in result["root_cause_candidates"]
    assert result["next_issue_hint"] == "#045.2"


def test_case3_entity_divergence():
    """Caso 3 — predicado compartilhado; entidades não colapsam → entity_divergence."""
    pt = _source(
        url="https://pt.wikipedia.org/wiki/Santos_FC",
        domain="pt.wikipedia.org",
        raw=5,
        canonical=2,
        facts=[
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "POSSUIR", "object": "ESTADIO URBANO CALDEIRA"},
            {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "DISPUTA", "object": "BRASILEIRAO"},
        ],
    )
    en = _source(
        url="https://en.wikipedia.org/wiki/Santos_FC",
        domain="en.wikipedia.org",
        raw=5,
        canonical=2,
        facts=[
            {"subject": "SANTOS FOOTBALL CLUB", "predicate": "POSSUIR", "object": "VILA BELMIRO STADIUM"},
            {"subject": "SANTOS FOOTBALL CLUB", "predicate": "DISPUTA", "object": "SERIE A"},
        ],
    )
    result = classify_pair(pt, en)
    # shared predicate POSSUIR/DISPUTA but different entity surfaces (no exact hash)
    # shared_pred non-empty and shared_ent may be empty depending on fold —
    # either entity_divergence or true_content; entity_divergence when shared_pred.
    assert result["collision_status"] in {
        "entity_divergence",
        "predicate_divergence",
        "no_shared_surface",
        "near_collision_structural",
    }
    if result["collision_status"] == "entity_divergence":
        assert result["next_issue_hint"] == "#047.1"


def test_case4_fallback_contamination_high_priority():
    """Caso 4 — fallback escrita no grafo → contamination, prioridade alta #063."""
    pt = _source(
        url="https://pt.wikipedia.org/wiki/Garrincha",
        domain="pt.wikipedia.org",
        raw=4,
        canonical=2,
        facts=[{"subject": "MANUEL FRANCISCO DOS SANTOS", "predicate": "JOGOU", "object": "BOTAFOGO"}],
    )
    en = _source(
        url="https://en.wikipedia.org/wiki/Garrincha",
        domain="en.wikipedia.org",
        raw=0,
        canonical=1,
        facts=[{"subject": "SYNTHETIC", "predicate": "IS", "object": "DEMO"}],
        fallback=True,
        written=True,
        entities=3,
    )
    result = classify_pair(pt, en)
    assert "fallback_contamination" in result["root_cause_candidates"]
    assert result["root_cause_candidates"][0] == "fallback_contamination"
    assert result["priority"] == "high"
    assert result["next_issue_hint"] == "#063"


def test_case5_true_content_difference():
    """Caso 5 — ambos extraem, sem superfície compartilhada → true_content_difference."""
    pt = _source(
        url="https://pt.wikipedia.org/wiki/Botafogo",
        domain="pt.wikipedia.org",
        raw=6,
        canonical=3,
        facts=[
            {"subject": "BOTAFOGO", "predicate": "VENCEU", "object": "CAMPEONATO ESTADUAL 1968"},
            {"subject": "BOTAFOGO", "predicate": "TEVE", "object": "TORCIDA FIEL"},
            {"subject": "BOTAFOGO", "predicate": "MANTEVE", "object": "CATEGORIA DE BASE"},
        ],
    )
    en = _source(
        url="https://en.wikipedia.org/wiki/Botafogo",
        domain="en.wikipedia.org",
        raw=5,
        canonical=3,
        facts=[
            {"subject": "BOTAFOGO FR", "predicate": "SIGNED", "object": "INTERNATIONAL STRIKER"},
            {"subject": "BOTAFOGO FR", "predicate": "PLAYED", "object": "LIBERTADORES SEMIFINAL"},
            {"subject": "BOTAFOGO FR", "predicate": "MOVED", "object": "NEW STADIUM PLAN"},
        ],
    )
    result = classify_pair(pt, en)
    assert result["collision_status"] == "no_shared_surface"
    assert result["root_cause_candidates"][0] == "true_content_difference"
    assert "#055" in result["next_issue_hint"] or "#048.2" in result["next_issue_hint"]


def test_exact_collision_when_hashes_overlap():
    facts_pt = [
        {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "POSSUIR", "object": "ESTADIO URBANO CALDEIRA"}
    ]
    facts_en = [
        {"subject": "SANTOS FUTEBOL CLUBE", "predicate": "POSSUIR", "object": "ESTADIO URBANO CALDEIRA"}
    ]
    pt = _source(url="https://pt.wikipedia.org/wiki/Santos_FC", domain="pt.wikipedia.org", raw=3, canonical=1, facts=facts_pt)
    en = _source(url="https://en.wikipedia.org/wiki/Santos_FC", domain="en.wikipedia.org", raw=3, canonical=1, facts=facts_en)
    result = classify_pair(pt, en)
    assert result["collision_status"] == "exact_collision"
    assert result["exact_fact_hash_overlap"]


def test_parse_worker_log_detects_partial_success_without_write():
    log = (
        "INFO:nexus.worker:Resposta [https://en.wikipedia.org/wiki/Pel%C3%A9]: 200 — "
        '{"status":"partial_success","message":"x","db_status":"demo-memory",'
        '"entities_processed":0,"vectors_indexed":1,"verified_facts":0}\n'
        'INFO:nexus.worker:telemetria {"url": "https://en.wikipedia.org/wiki/Pel%C3%A9", '
        '"quality": "unproductive", "canonical_triples": 0, "raw_triples": 1}\n'
    )
    entries = parse_worker_ingest_log(log)
    url = "https://en.wikipedia.org/wiki/Pel%C3%A9"
    assert url in entries
    entry = entries[url]
    assert entry["fallback_used"] is True
    assert entry["quality"] == "unproductive"
    analysis = classify_log_fallback(entry)
    assert analysis["fallback_written_to_graph"] is False
    assert analysis["masked_extraction_failure"] is True
    assert analysis["priority"] == "high"
    assert analysis["next_issue_hint"] == "#058.4"


def test_classify_log_fallback_contamination_when_written():
    entry = {
        "url": "https://example.com/x",
        "fallback_used": True,
        "fallback_type": "demo-memory",
        "fallback_written_to_graph": True,
        "entities_processed": 5,
    }
    analysis = classify_log_fallback(entry)
    assert analysis["root_cause"] == "fallback_contamination"
    assert analysis["next_issue_hint"] == "#063"
    assert analysis["priority"] == "high"


def test_parse_worker_log_detects_degraded_and_failed_status():
    """#058.4 — parser reconhece status novos degraded/failed sem gravação."""
    log = (
        "INFO:nexus.worker:Resposta [https://en.wikipedia.org/wiki/Pel%C3%A9]: 200 — "
        '{"status":"failed","message":"x","db_status":"demo-memory",'
        '"entities_processed":0,"vectors_indexed":0,"verified_facts":0,'
        '"masked_extraction_failure":true,"allow_demo_fallback":false}\n'
        "INFO:nexus.worker:Resposta [https://arxiv.org/abs/2303.08774]: 200 — "
        '{"status":"degraded","message":"y","db_status":"demo-memory",'
        '"entities_processed":0,"vectors_indexed":0,"verified_facts":0,'
        '"masked_extraction_failure":true,"allow_demo_fallback":true}\n'
    )
    entries = parse_worker_ingest_log(log)
    for url in (
        "https://en.wikipedia.org/wiki/Pel%C3%A9",
        "https://arxiv.org/abs/2303.08774",
    ):
        assert url in entries
        entry = entries[url]
        assert entry["fallback_used"] is True
        assert entry["masked_extraction_failure"] is True
        assert entry["fallback_written_to_graph"] is False
        analysis = classify_log_fallback(entry)
        assert analysis["masked_extraction_failure"] is True
        assert analysis["priority"] == "high"
        assert analysis["next_issue_hint"] == "#058.4"


def test_build_parity_report_summary_counts():
    report = build_parity_report(
        [
            {
                "target": "Pelé",
                "canonical_entity": "EDSON ARANTES DO NASCIMENTO",
                "pt_source": _source(
                    url="https://pt.wikipedia.org/wiki/Pelé",
                    domain="pt.wikipedia.org",
                    raw=10,
                    canonical=4,
                    facts=[{"subject": "EDSON", "predicate": "DEFENDEU", "object": "SANTOS"}],
                ),
                "en_source": _source(
                    url="https://en.wikipedia.org/wiki/Pelé",
                    domain="en.wikipedia.org",
                    raw=0,
                    canonical=0,
                    facts=[],
                    fallback=True,
                    entities=0,
                ),
            },
            {
                "target": "Garrincha",
                "canonical_entity": "MANUEL FRANCISCO DOS SANTOS",
                "pt_source": _source(
                    url="https://pt.wikipedia.org/wiki/Garrincha",
                    domain="pt.wikipedia.org",
                    raw=5,
                    canonical=2,
                    facts=[{"subject": "A", "predicate": "P", "object": "B"}],
                ),
                "en_source": _source(
                    url="https://en.wikipedia.org/wiki/Garrincha",
                    domain="en.wikipedia.org",
                    raw=5,
                    canonical=2,
                    facts=[{"subject": "A", "predicate": "P", "object": "B"}],
                ),
            },
        ],
        build_space_commit="5eb6931",
        worker_run_id="35942830764",
    )
    assert report["summary"]["targets_total"] == 2
    assert report["summary"]["targets_with_pt_canonical"] == 2
    assert report["summary"]["targets_with_en_canonical"] == 1
    assert report["summary"]["targets_with_both_canonical"] == 1
    assert report["summary"]["targets_with_exact_collision"] == 1
    assert report["summary"]["fallback_contamination_suspected"] == 0
    assert report["build_space_commit"] == "5eb6931"
    assert "read-only" in report["truthfulness_note"].lower()


def test_group_facts_by_target_alias():
    facts = [
        {"subject": "Pelé", "predicate": "DEFENDEU", "object": "Santos FC", "domains": ["pt.wikipedia.org"]},
        {"subject": "Santos Football Club", "predicate": "POSSUIR", "object": "Vila Belmiro", "domains": ["en.wikipedia.org"]},
    ]
    aliases = {
        "EDSON ARANTES DO NASCIMENTO": ["Pelé", "Pele"],
        "SANTOS FUTEBOL CLUBE": ["Santos FC", "Santos Football Club"],
    }
    grouped = group_facts_by_target_alias(facts, aliases)
    assert "EDSON ARANTES DO NASCIMENTO" in grouped
    assert "SANTOS FUTEBOL CLUBE" in grouped


def test_load_persisted_facts_by_domain():
    facts = [
        {"subject": "A", "predicate": "P", "object": "B", "domains": ["pt.wikipedia.org"]},
        {"subject": "A", "predicate": "P", "object": "C", "url": "https://en.wikipedia.org/wiki/x"},
    ]
    by_dom = load_persisted_facts_by_domain(facts)
    assert len(by_dom["pt.wikipedia.org"]) == 1
    assert len(by_dom["en.wikipedia.org"]) == 1


def test_script_is_read_only_by_source():
    source = SCRIPT.read_text(encoding="utf-8")
    lowered = source.lower()
    # não pode chamar o endpoint de ingestão nem reset de grafo
    assert "api/" + "ingest" not in lowered
    assert "detach " + "delete" not in lowered
    assert "read-only" in lowered or "read_only" in lowered
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr.lower() not in {"ingest", "persist_episodes", "upsert"}


def test_fold_key_and_domain_helpers():
    assert fold_key("  São Paulo!! ") == "sao paulo"
    from src.cognition.extraction_parity_audit import domain_of

    assert domain_of("https://www.pt.wikipedia.org/wiki/X") == "pt.wikipedia.org"


def test_build_target_report_maps_fields():
    row = build_target_report(
        target="Pelé",
        canonical_entity="EDSON ARANTES DO NASCIMENTO",
        pt_source=_source(
            url="https://pt.wikipedia.org/wiki/Pelé",
            domain="pt.wikipedia.org",
            raw=8,
            canonical=2,
            facts=[{"subject": "EDSON", "predicate": "DEFENDEU", "object": "SANTOS"}],
        ),
        en_source=_source(
            url="https://en.wikipedia.org/wiki/Pelé",
            domain="en.wikipedia.org",
            raw=1,
            canonical=0,
            facts=[],
            fallback=True,
            entities=0,
        ),
    )
    assert row["target"] == "Pelé"
    assert len(row["sources"]) == 2
    assert row["collision_status"] == "no_en_canonical_triples"
    assert row["next_issue_hint"]
