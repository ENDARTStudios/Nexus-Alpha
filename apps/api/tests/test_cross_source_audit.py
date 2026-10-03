"""Testes da auditoria de near-match cross-source (#046) — puros, sem Neo4j."""
from src.cognition.cross_source_audit import (
    audit,
    classify_near_match,
    similarity,
)


def test_similarity_word_order_and_garbage():
    assert similarity("Santos FC", "FC Santos") == 1.0
    assert similarity("Estadio Urbano Caldeira", "Urbano Caldeira Estadio") == 1.0
    assert similarity("", "qualquer") == 0.0
    assert similarity("rede neural", "cebola roxa") < 0.4


def test_classify_subject_variant_high():
    left = {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["a.com"]}
    right = {"subject": "FC Santos", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["b.com"]}
    assert classify_near_match(left, right) == ("high", "subject_variant")


def test_classify_object_variant_high():
    left = {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["a.com"]}
    right = {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Urbano Caldeira Estadio", "domains": ["b.com"]}
    assert classify_near_match(left, right) == ("high", "object_variant")


def test_classify_predicate_variant_medium():
    left = {"subject": "Gato", "predicate": "UTILIZA", "object": "Caixa", "domains": ["a.com"]}
    right = {"subject": "Gato", "predicate": "CONECTA_A", "object": "Caixa", "domains": ["b.com"]}
    assert classify_near_match(left, right) == ("medium", "predicate_variant")


def test_same_domain_is_not_cross_source():
    left = {"subject": "Santos FC", "predicate": "POSSUIR", "object": "X", "domains": ["a.com"]}
    right = {"subject": "FC Santos", "predicate": "POSSUIR", "object": "X", "domains": ["a.com"]}
    assert classify_near_match(left, right) == (None, None)


def _facts():
    return [
        {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["a.com"]},
        {"subject": "FC Santos", "predicate": "POSSUIR", "object": "Estadio Urbano Caldeira", "domains": ["b.com"]},
        {"subject": "Santos FC", "predicate": "POSSUIR", "object": "Urbano Caldeira Estadio", "domains": ["c.com"]},
        {"subject": "Rede Neural", "predicate": "UTILIZA", "object": "Gradiente Descendente", "domains": ["d.com"]},
        {"subject": "Topico Isolado", "predicate": "CONECTA_A", "object": "Outro Topico", "domains": ["e.com"]},
    ]


def test_audit_counts_and_cluster_reaching_quorum():
    report = audit(_facts(), quorum=3)
    assert report["facts_total"] == 5
    assert report["facts_with_one_domain"] == 5
    assert report["exact_cross_source_matches"] == 0
    assert report["near_matches"]["high"] == 3
    assert report["mismatch_types"]["subject_variant"] + report["mismatch_types"]["object_variant"] == 3
    assert report["mismatch_types"]["true_unique"] == 2
    assert report["potential_verified_if_linking"] == 1
    assert report["near_match_rate_high"] == 0.6
    assert report["top_examples"], "deve haver exemplos de near-match high"


def test_audit_is_read_only_and_reports_no_promotion():
    facts = _facts()
    snapshot = [dict(f) for f in facts]
    audit(facts, quorum=3)
    assert facts == snapshot, "audit não pode mutar as entradas"


def test_audit_no_cross_source_when_all_unique():
    facts = [
        {"subject": "A", "predicate": "UTILIZA", "object": "B", "domains": ["x.com"]},
        {"subject": "C", "predicate": "CONECTA_A", "object": "D", "domains": ["y.com"]},
    ]
    report = audit(facts, quorum=3)
    assert report["near_matches"]["high"] == 0
    assert report["potential_verified_if_linking"] == 0
    assert report["mismatch_types"]["true_unique"] == 2
