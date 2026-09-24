"""Testes do script de inspeção cross-lingual — puros, sem rede/Neo4j."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import inspect_cross_lingual_divergence as insp  # noqa: E402


def test_script_is_read_only_by_source():
    """Script de inspeção não pode chamar ingest/escrita de grafo."""
    source = (SCRIPTS / "inspect_cross_lingual_divergence.py").read_text(encoding="utf-8")
    text_lower = source.lower()
    assert "api/ingest" not in text_lower
    assert "persist_episodes" not in text_lower
    assert "detached delete" not in text_lower and "detach delete" not in text_lower
    assert "read_only" in text_lower or "read-only" in text_lower
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr.lower() not in {"persist_episodes", "ingest", "upsert"}


def test_fact_key_is_stable_and_sixteen_hex_chars():
    a = insp.fact_key("Santos FC", "DEFENDEU", "Pelé")
    b = insp.fact_key("Santos FC", "DEFENDEU", "Pelé")
    c = insp.fact_key("Santos Football Club", "DEFENDEU", "Pelé")
    assert a == b
    assert a != c
    assert len(a) == 16
    assert all(ch in "0123456789abcdef" for ch in a)


def test_classify_flags_only_h4_when_strings_normalize_equal():
    hyp, issue = insp.classify(
        [
            {
                "field": "subject",
                "pt": "Santos FC",
                "en": "SANTOS  FC",
                "raw_pt": "Santos FC",
                "raw_en": "SANTOS  FC",
                "overlap": [],
            }
        ]
    )
    assert "H4" in hyp
    assert "normaliza" in issue.lower() or "normaliz" in issue.lower()


def test_classify_detects_predicate_and_entity_divergence():
    hyp, issue = insp.classify(
        [
            {"field": "predicate", "pt": "SER", "en": "DEFENDEU", "raw_pt": "foi", "raw_en": "played for", "overlap": []},
            {"field": "subject", "pt": "PELE", "en": "PELE SAID HE", "raw_pt": "Pelé", "raw_en": "Pelé said he", "overlap": ["PELE"]},
        ]
    )
    assert "H1" in hyp and "H2" in hyp
    assert "#047" in issue


def test_classify_entity_only_recommends_047():
    hyp, issue = insp.classify(
        [
            {
                "field": "subject",
                "pt": "TIME SANTISTA",
                "en": "MY TIME IN FOOTBALL",
                "raw_pt": "time santista",
                "raw_en": "My time in football",
                "overlap": ["TIME"],
            }
        ]
    )
    assert "H1" in hyp
    assert issue == "#047"


def test_targets_cover_five_offline_pairs():
    assert set(insp.TARGETS) == {
        "santos_fc",
        "estadio_urbano_caldeira",
        "pele",
        "garrincha",
        "botafogo",
    }
    for pair in insp.TARGETS.values():
        assert pair["pt"].startswith("https://pt.wikipedia.org/")
        assert pair["en"].startswith("https://en.wikipedia.org/")


def test_findings_doc_exists_and_mentions_h3():
    doc = (ROOT / "docs" / "INSPECTION_2_FINDINGS.md").read_text(encoding="utf-8")
    assert "H3" in doc
    assert "shared_canonical_keys" in doc or "shared" in doc.lower()
    assert "#047" in doc
    assert "#058.2" in doc
