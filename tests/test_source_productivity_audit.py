"""Testes da auditoria de produtividade de fontes (#058) — puros, sem rede."""
from __future__ import annotations

import json
from pathlib import Path

from src.cognition.entity_linking_audit import (
    FORBIDDEN_MARKERS,
    assert_no_secret_markers,
)
from src.miner.seed_loader import FORBIDDEN_DOMAINS, load_seed_clusters, validate_seed_clusters
from src.miner.source_productivity import (
    MIN_CLEANED_TEXT,
    analyze_text,
    classify_extractive_quality,
    detect_football_verbs,
    split_sentences,
    summarize,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_source_productivity.py"
MANIFEST = ROOT / "config" / "seed_clusters.yaml"

DECLARATIVE = (
    "O Santos FC e um clube brasileiro fundado em 1912. "
    "O clube possui o Estadio Urbano Caldeira em Santos. "
    "O estadio fica localizado no bairro da Vila Belmiro. "
    "A equipe disputa o Campeonato Brasileiro e tem grande torcida. "
    "Pele defendeu o Santos FC durante toda a sua carreira profissional. "
    "Garrincha jogou pelo Botafogo antes de se tornar campeao mundial. "
    "O Botafogo e um clube do Rio de Janeiro com historia no futebol. "
    "A torcida do Santos e considerada a segunda maior do Brasil. "
    "O estadio ja recebeu partidas internacionais importantes. "
    "O clube possui categorias de base e um museu proprio. "
)


def _report(**over):
    base = {
        "url": "https://example.com/x",
        "status": 200,
        "cleaned_text_length": 5000,
        "raw_triples": 8,
        "canonical_triples": 5,
        "rejected_noise": 3,
        "rejection_reasons": {"unmapped_predicate": 2, "missing_entity": 1},
        "football_related_hits": 2,
        "extractive_quality": "productive",
    }
    base.update(over)
    return base


def test_classify_productive():
    assert classify_extractive_quality(_report()) == "productive"


def test_classify_unproductive_when_zero_canonical_or_short_text():
    assert classify_extractive_quality(_report(canonical_triples=0)) == "unproductive"
    assert classify_extractive_quality(
        _report(cleaned_text_length=MIN_CLEANED_TEXT - 1)
    ) == "unproductive"


def test_classify_weak_when_one_or_two_canonical():
    assert classify_extractive_quality(_report(canonical_triples=2)) == "weak"


def test_classify_weak_when_navigation_noise_dominated():
    report = _report(
        rejected_noise=10,
        rejection_reasons={"object_prepositional_phrase": 8, "object_date_like": 2},
    )
    assert classify_extractive_quality(report) == "weak"


def test_classify_weak_when_football_required_and_absent():
    report = _report(football_related_hits=0, require_football=False)
    assert classify_extractive_quality(report, require_football=False) == "productive"
    assert classify_extractive_quality(report, require_football=True) == "weak"


def test_split_sentences_counts_declarative_sentences():
    sentences = split_sentences(DECLARATIVE)
    assert len(sentences) >= 8
    assert all(sentence.endswith(".") for sentence in sentences)


def test_detect_football_verbs_evidence_for_backlog():
    verbs = detect_football_verbs(DECLARATIVE)
    assert "defendeu" in verbs
    assert "jogou" in verbs
    assert detect_football_verbs("A IA utiliza dados.") == []


def test_analyze_text_reports_counts_and_quality():
    report = analyze_text(DECLARATIVE, url="https://pt.wikipedia.org/wiki/Santos_FC")
    assert report["url"] == "https://pt.wikipedia.org/wiki/Santos_FC"
    assert report["raw_triples"] >= 1
    assert report["canonical_triples"] >= 1
    assert report["sentences_considered"] >= 8
    assert report["football_verb_hits"] >= 2
    assert report["extractive_quality"] in {"productive", "weak", "unproductive"}
    assert set(report["rejection_reasons"]) <= {
        "ok", "missing_entity", "unmapped_predicate", "invalid_predicate",
        "modal_predicate", "ambiguous_predicate", "self_loop",
        "nonverbal_predicate", "stopword_predicate", "numeric_predicate",
        "url_or_code_predicate", "object_date_like", "object_prepositional_phrase",
        "object_adverbial_phrase", "object_pronoun", "object_clause_fragment",
        "object_punctuated", "object_numeric_only", "object_generic_phrase",
        "subject_generic_phrase", "subject_clause_fragment",
        "subject_starts_with_stopword", "subject_too_long", "subject_quantifier_phrase",
    }


def test_analyze_text_is_read_only_on_inputs():
    text = DECLARATIVE
    snapshot = str(text)
    analyze_text(text, url="https://example.com")
    assert text == snapshot


def test_golden_case_possuir_spans_are_canonical():
    report = analyze_text(
        "O Santos FC possui o Estadio Urbano Caldeira.",
        url="https://pt.wikipedia.org/wiki/Santos_FC",
    )
    assert report["canonical_triples"] == 1
    assert "SANTOS FC" in report["top_subjects"]
    assert "ESTADIO URBANO CALDEIRA" in report["top_objects"]
    assert report["top_predicates"] == {"POSSUIR": 1}


def test_golden_case_football_verb_is_visible_even_if_unmapped():
    report = analyze_text("Pele defendeu o Santos FC.", url="https://example.com")
    assert report["football_verb_hits"] >= 1
    assert "defendeu" in report["detected_football_verbs"]
    assert report["extractive_quality"] == "unproductive"
    assert report["notes"]


def test_empty_text_is_unproductive():
    report = analyze_text("", url="https://example.com", status=404, content_length=0)
    assert report["extractive_quality"] == "unproductive"
    assert report["canonical_triples"] == 0
    assert report["cleaned_text_length"] == 0


def test_summarize_aggregates_lote():
    reports = [
        _report(url="https://a.com/1"),
        _report(url="https://b.com/2", canonical_triples=0, extractive_quality="unproductive"),
        _report(url="https://a.com/3"),
    ]
    summary = summarize(reports)
    assert summary["urls_evaluated"] == 3
    assert summary["quality"]["productive"] == 2
    assert summary["quality"]["unproductive"] == 1
    assert summary["urls_by_domain"]["a.com"] == 2
    assert summary["total_canonical_triples"] == 10


def test_script_is_read_only_no_neo4j_no_qdrant_no_ingest():
    import ast
    import re

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            if isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))

    imports: list[str] = []
    strings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                strings.append(node.value)

    joined = " ".join(imports).lower()
    assert "neo4j" not in joined
    assert "qdrant" not in joined
    for value in strings:
        low = value.lower()
        assert "/api/ingest" not in low, value
        assert re.search(r"\b(?:merge|create|delete|drop|load\s+csv)\s*\(", low) is None, value


def test_report_has_no_secret_markers():
    report = analyze_text(DECLARATIVE, url="https://example.com")
    text = json.dumps(report, ensure_ascii=False)
    assert assert_no_secret_markers(text, FORBIDDEN_MARKERS) == []


def test_shipped_manifest_still_valid_after_replacement():
    assert validate_seed_clusters(load_seed_clusters(MANIFEST)) == []


def test_betting_and_social_domains_are_forbidden():
    for domain in ("bet365.com", "sportingbet.com", "twitter.com", "youtube.com"):
        assert domain in FORBIDDEN_DOMAINS
