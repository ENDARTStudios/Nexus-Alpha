"""Testes #058.5 — forense de extração cross-lingual (puros, sem rede/Neo4j)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cognition.extraction_forensics import (  # noqa: E402
    DIAGNOSIS_STAGES,
    NEXT_STAGE_ISSUES,
    build_comparison,
    build_forensics_report,
    build_source_forensics,
    classify_diagnosis,
    evaluate_hypotheses,
    looks_like_wikipedia_404,
)

SCRIPT = ROOT / "scripts" / "audit_botafogo_en_extraction.py"


def test_diagnosis_stages_complete():
    assert DIAGNOSIS_STAGES == (
        "fetch",
        "cleaning",
        "sentence_selection",
        "extraction",
        "span_validation",
        "predicate_mapping",
        "entity_aliasing",
        "persistence",
        "unknown",
    )
    for stage in DIAGNOSIS_STAGES:
        assert stage in NEXT_STAGE_ISSUES


def test_looks_like_wikipedia_404_true_on_error_page():
    sample = (
        "Consider adding a redirect here to the correct title. "
        "If the page has been deleted, check the deletion log , and see "
        "Why was the page I created deleted?"
    )
    assert looks_like_wikipedia_404(sample) is True


def test_looks_like_wikipedia_404_false_on_article():
    sample = (
        "Botafogo de Futebol e Regatas is a Brazilian professional football "
        "club based in Rio de Janeiro. The club was founded in 1904."
    )
    assert looks_like_wikipedia_404(sample) is False


def test_looks_like_wikipedia_404_false_on_empty():
    assert looks_like_wikipedia_404("") is False
    assert looks_like_wikipedia_404(None) is False  # type: ignore[arg-type]


def test_diagnose_fetch_status_404():
    result = classify_diagnosis({
        "fetch_status": 404,
        "cleaned_text_length": 2116,
        "sentences_considered": 25,
        "sentences_scored_above_threshold": 10,
        "raw_triples": 1,
        "canonical_triples": 1,
        "rejected_reasons": {},
        "text_sample": (
            "If the page has been deleted, check the deletion log. "
            "Consider adding a redirect here."
        ),
        "top_raw_subjects": ["If the page"],
        "persisted_fact_hashes": [],
    })
    assert result["diagnosis"] == "fetch"
    assert result["next_issue_hint"] == "#048.3"
    assert result["is_unknown"] is False
    assert any("fetch_status=404" in e for e in result["evidence"])


def test_diagnose_fetch_status_zero_network_error():
    result = classify_diagnosis({
        "fetch_status": 0,
        "cleaned_text_length": 0,
        "raw_triples": 0,
        "canonical_triples": 0,
        "rejected_reasons": {},
    })
    assert result["diagnosis"] == "fetch"
    assert result["next_issue_hint"] == "#048.3"


def test_diagnose_cleaning_too_short():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 120,
        "sentences_considered": 3,
        "sentences_scored_above_threshold": 1,
        "raw_triples": 0,
        "canonical_triples": 0,
        "rejected_reasons": {},
        "text_sample": "Short page.",
    })
    assert result["diagnosis"] == "cleaning"
    assert result["next_issue_hint"] == "#058.6"


def test_diagnose_extraction_zero_raw_with_text():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 5000,
        "sentences_considered": 40,
        "sentences_scored_above_threshold": 20,
        "raw_triples": 0,
        "canonical_triples": 0,
        "rejected_reasons": {},
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "extraction"
    assert result["next_issue_hint"] == "#058.8"
    assert "sentence_selection" in result["secondary_candidates"]


def test_diagnose_sentence_selection_when_scored_zero():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 5000,
        "sentences_considered": 40,
        "sentences_scored_above_threshold": 0,
        "raw_triples": 0,
        "canonical_triples": 0,
        "rejected_reasons": {},
        "text_sample": "Many sentences but none score above threshold. " * 20,
    })
    assert result["diagnosis"] == "sentence_selection"
    assert result["next_issue_hint"] == "#058.7"


def test_diagnose_span_validation_dominant():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 10,
        "canonical_triples": 0,
        "rejected_reasons": {
            "subject_generic_phrase": 5,
            "object_clause_fragment": 3,
            "missing_entity": 2,
        },
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "span_validation"
    assert result["next_issue_hint"] == "#058.9"
    assert "predicate_mapping" in result["secondary_candidates"]


def test_diagnose_predicate_mapping_dominant():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 8,
        "canonical_triples": 0,
        "rejected_reasons": {
            "unmapped_predicate": 6,
            "invalid_predicate": 2,
        },
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "predicate_mapping"
    assert result["next_issue_hint"] == "#045.3"


def test_diagnose_entity_aliasing_missing_entity():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 5,
        "canonical_triples": 0,
        "rejected_reasons": {"missing_entity": 5},
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "entity_aliasing"
    assert result["next_issue_hint"] == "#047.2"


def test_diagnose_unknown_when_healthy_without_graph():
    """Forense default (sem grafo) não diagnostica persistence."""
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 10,
        "canonical_triples": 4,
        "rejected_reasons": {},
        "top_raw_subjects": ["Botafogo de Futebol e Regatas"],
        "persisted_fact_hashes": None,  # grafo não consultado
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "unknown"
    assert result["is_unknown"] is True
    assert any("nao checado" in e or "não checado" in e or "saudavel" in e for e in result["evidence"])


def test_diagnose_persistence_when_graph_checked_empty():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 10,
        "canonical_triples": 4,
        "rejected_reasons": {},
        "top_raw_subjects": ["Botafogo de Futebol e Regatas"],
        "persisted_fact_hashes": [],  # grafo checado e vazio
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "persistence"
    assert result["next_issue_hint"] == "#055/#048.2/#065"


def test_diagnose_generic_subjects_flagged():
    result = classify_diagnosis({
        "fetch_status": 200,
        "cleaned_text_length": 8000,
        "sentences_considered": 60,
        "sentences_scored_above_threshold": 30,
        "raw_triples": 10,
        "canonical_triples": 3,
        "rejected_reasons": {},
        "top_raw_subjects": [
            "the club",
            "a Brazilian professional football club",
            "the team",
        ],
        "persisted_fact_hashes": ["abc"],
        "text_sample": "A long article about a football club. " * 30,
    })
    assert result["diagnosis"] == "span_validation"
    assert result["next_issue_hint"] == "#058.9"
    assert any("genéricos" in e or "genericos" in e for e in result["evidence"])


def test_build_source_forensics_botafogo_404_case():
    """Caso real Botafogo EN: HTTP 404 + marcadores de página de erro."""
    src = build_source_forensics(
        url="https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        fetch_status=404,
        final_url="https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        content_length=51138,
        cleaned_text_length=2116,
        sentences_considered=25,
        sentences_scored_above_threshold=10,
        raw_triples=1,
        canonical_triples=1,
        rejected_reasons={},
        top_raw_subjects=["If the page"],
        top_raw_objects=["been deleted"],
        top_raw_predicates=["POSSUIR"],
        text_sample=(
            "Consider adding a redirect here to the correct title. "
            "If the page has been deleted, check the deletion log."
        ),
        ingested=False,
    )
    assert src["fetch_status"] == 404
    assert src["diagnosis"] == "fetch"
    assert src["next_issue_hint"] == "#048.3"
    assert src["looks_like_wikipedia_404"] is True
    assert src["raw_triples"] == 1
    assert src["canonical_triples"] == 1


def test_build_comparison_fetch_failure():
    pt = build_source_forensics(
        url="https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        fetch_status=200,
        cleaned_text_length=101868,
        sentences_considered=1251,
        sentences_scored_above_threshold=600,
        raw_triples=25,
        canonical_triples=13,
        rejected_reasons={"missing_entity": 7},
        top_raw_subjects=["Botafogo de Futebol e Regatas"],
        text_sample="Botafogo de Futebol e Regatas is a Brazilian club. " * 30,
    )
    en = build_source_forensics(
        url="https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        fetch_status=404,
        cleaned_text_length=2116,
        raw_triples=1,
        canonical_triples=1,
        top_raw_subjects=["If the page"],
        text_sample=(
            "If the page has been deleted, check the deletion log. "
            "Consider adding a redirect here."
        ),
    )
    comparison = build_comparison(pt, en)
    assert comparison["collision_status"] == "en_fetch_failed"
    assert comparison["root_cause_candidates"] == ["fetch"]
    assert comparison["next_issue_hints"] == ["#048.3"]
    assert comparison["en_diagnosis"] == "fetch"
    assert comparison["pt_diagnosis"] in DIAGNOSIS_STAGES


def test_build_forensics_report_and_hypotheses():
    pt = build_source_forensics(
        url="https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        fetch_status=200,
        cleaned_text_length=101868,
        raw_triples=25,
        canonical_triples=13,
        top_raw_subjects=["Botafogo de Futebol e Regatas"],
        persisted_fact_hashes=[],
        text_sample="Botafogo de Futebol e Regatas is a Brazilian club. " * 30,
    )
    en = build_source_forensics(
        url="https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        fetch_status=404,
        cleaned_text_length=2116,
        raw_triples=1,
        canonical_triples=1,
        top_raw_subjects=["If the page"],
        text_sample=(
            "If the page has been deleted, check the deletion log. "
            "Consider adding a redirect here."
        ),
    )
    comparison = build_comparison(pt, en)
    hypotheses = evaluate_hypotheses(pt, en)
    report = build_forensics_report(
        target="BOTAFOGO DE FUTEBOL E REGATAS",
        sources=[pt, en],
        comparison=comparison,
        hypotheses=hypotheses,
        audit_id="botafogo_en_extraction_forensics_2026-09-24",
        quorum=3,
    )
    assert report["audit_id"] == "botafogo_en_extraction_forensics_2026-09-24"
    assert report["target"] == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert len(report["sources"]) == 2
    assert report["diagnosis_summary"]["primary_diagnosis"] == "fetch"
    assert report["diagnosis_summary"]["next_issue_hint"] == "#048.3"
    assert report["diagnosis_summary"]["is_unknown"] is False
    assert report["quorum"] == 3
    # H1 (URL improdutive/404) deve ser suportada.
    h1 = next(h for h in hypotheses if h["id"] == "H1")
    assert h1["supported"] is True
    assert h1["next_issue"] == "#048.3"
    assert "Neo4j" not in report["truthfulness_note"] or "does not" in report["truthfulness_note"]


def test_evaluate_hypotheses_h1_supported_on_404():
    pt = build_source_forensics(
        url="https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        fetch_status=200,
        cleaned_text_length=101868,
        raw_triples=25,
        canonical_triples=13,
        text_sample="Botafogo is a club. " * 50,
    )
    en = build_source_forensics(
        url="https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
        fetch_status=404,
        cleaned_text_length=2116,
        raw_triples=1,
        canonical_triples=1,
        text_sample=(
            "If the page has been deleted, check the deletion log. "
            "Consider adding a redirect here."
        ),
    )
    hyps = evaluate_hypotheses(pt, en)
    by_id = {h["id"]: h for h in hyps}
    assert by_id["H1"]["supported"] is True
    assert by_id["H4"]["supported"] is False  # não é extraction — é fetch
    assert by_id["H7"]["supported"] is False  # alias só depois de H1–H6


def test_evaluate_hypotheses_h4_when_extraction_fails():
    pt = build_source_forensics(
        url="https://pt.wikipedia.org/wiki/x",
        fetch_status=200,
        cleaned_text_length=50000,
        raw_triples=20,
        canonical_triples=10,
        text_sample="Article. " * 100,
    )
    en = build_source_forensics(
        url="https://en.wikipedia.org/wiki/y",
        fetch_status=200,
        cleaned_text_length=9000,
        sentences_considered=80,
        sentences_scored_above_threshold=40,
        raw_triples=0,
        canonical_triples=0,
        rejected_reasons={},
        text_sample="A long English article about football. " * 40,
    )
    hyps = evaluate_hypotheses(pt, en)
    by_id = {h["id"]: h for h in hyps}
    assert by_id["H4"]["supported"] is True
    assert by_id["H1"]["supported"] is False
    comparison = build_comparison(pt, en)
    assert comparison["en_diagnosis"] == "extraction"


def test_script_is_read_only_by_source():
    source = SCRIPT.read_text(encoding="utf-8")
    lowered = source.lower()
    assert "api/" + "ingest" not in lowered
    assert "detach " + "delete" not in lowered
    assert "read-only" in lowered or "read_only" in lowered
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr.lower() not in {
                "ingest",
                "persist_episodes",
                "upsert",
                "detach_delete",
            }


def test_module_has_no_network_or_graph_imports():
    """Módulo puro não deve importar httpx/neo4j/qdrant."""
    module_path = ROOT / "src" / "cognition" / "extraction_forensics.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"httpx", "neo4j", "qdrant_client", "requests", "aiohttp"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert node.module.split(".")[0] not in forbidden


def test_next_issue_hints_cover_all_stages():
    for stage in DIAGNOSIS_STAGES:
        assert stage in NEXT_STAGE_ISSUES
        assert NEXT_STAGE_ISSUES[stage].startswith("#")
