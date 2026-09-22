"""Testes do canonicalizador semântico (colisão de entidades e predicados)."""
from __future__ import annotations

from src.cognition.canonicalizer import SemanticCanonicalizer


def test_triplet_canonicalization_logic():
    canonicalizer = SemanticCanonicalizer()
    raw = {"subject": "ia", "predicate": "utiliza", "object": "ml"}
    result = canonicalizer.canonicalize_triplet(raw)
    assert result["subject"] == "INTELIGÊNCIA ARTIFICIAL"
    assert result["predicate"] == "UTILIZA"
    assert result["object"] == "MACHINE LEARNING"


def test_fallback_unknown_terms():
    canonicalizer = SemanticCanonicalizer()
    raw = {"subject": "algoritmo quântico", "predicate": "acelera", "object": "processamento"}
    result = canonicalizer.canonicalize_triplet(raw)
    assert result["subject"] == "ALGORITMO QUÂNTICO"
    assert result["predicate"] == "ACELERA"


def test_acronyms_collide_with_full_names():
    canonicalizer = SemanticCanonicalizer()
    a = canonicalizer.canonicalize_triplet({"subject": "AI", "predicate": "usa", "object": "redes neurais"})
    b = canonicalizer.canonicalize_triplet(
        {"subject": "Inteligência Artificial", "predicate": "emprega", "object": "Redes Neurais"}
    )
    assert a["subject"] == b["subject"]
    assert a["predicate"] == b["predicate"]
    assert a["object"] == b["object"]


def test_expanded_entity_synonyms_collapse():
    c = SemanticCanonicalizer()
    for variant in ["ia", "AI", "artificial intelligence", "Inteligência Artificial", "inteligencia artificial"]:
        assert c.canonicalize_entity(variant) == "INTELIGÊNCIA ARTIFICIAL"


def test_domain_synonyms_map_to_controlled_entities():
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("nlp") == "PROCESSAMENTO DE LINGUAGEM NATURAL"
    assert c.canonicalize_entity("pln") == "PROCESSAMENTO DE LINGUAGEM NATURAL"
    assert c.canonicalize_entity("computer vision") == "VISÃO COMPUTACIONAL"
    assert c.canonicalize_entity("visão computacional") == "VISÃO COMPUTACIONAL"
    assert c.canonicalize_entity("genai") == "IA GENERATIVA"
    assert c.canonicalize_entity("rede_neural") == "REDES NEURAIS"


def test_predicate_synonyms_collapse_to_controlled():
    c = SemanticCanonicalizer()
    for verb in ["usa", "emprega", "utiliza", "usar", "use"]:
        assert c.canonicalize_predicate(verb) == "UTILIZA"
    for verb in ["cria", "gera", "produz"]:
        assert c.canonicalize_predicate(verb) == "PRODUZ"
    for verb in ["contém", "contem", "inclui"]:
        assert c.canonicalize_predicate(verb) == "CONTIENE"
    assert c.canonicalize_predicate("pertence_a") == "PERTENCE_A"


def test_normalization_strips_spaces_and_punctuation():
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("  redes   neurais  ") == "REDES NEURAIS"
    assert c.canonicalize_entity("ALGORITMO QUÂNTICO.") == "ALGORITMO QUÂNTICO"
