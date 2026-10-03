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
    # #041: desconhecidas colapsam para forma determinística UPPER foldada
    # (trade-off aprovado: acentos preservados só via dicionário).
    assert result["subject"] == "ALGORITMO QUANTICO"
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
    assert c.canonicalize_entity("ALGORITMO QUÂNTICO.") == "ALGORITMO QUANTICO"


def test_accent_variants_collapse_for_unknown_entities():
    # #041: variantes que diferem SÓ por acento colapsam (José/Jose, São Paulo/Sao Paulo, João/Joao).
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("José") == c.canonicalize_entity("Jose")
    assert c.canonicalize_entity("São Paulo") == c.canonicalize_entity("Sao Paulo")
    assert c.canonicalize_entity("João") == c.canonicalize_entity("Joao")
    assert c.canonicalize_entity("São Paulo") == "SAO PAULO"


def test_non_accent_token_differences_do_not_collapse():
    # Limitação honesta (#041): tokens distintos ("Clube" vs "Club") NÃO colapsam
    # por fold — exigem alias no dicionário ou entity linking vetorial (item 2).
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("Futebol Clube") != c.canonicalize_entity("Futebol Club")


def test_leading_articles_stripped_before_lookup():
    # #041: mesma regra do EntityExtractor — "A IA" ≡ "IA".
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("A IA") == "INTELIGÊNCIA ARTIFICIAL"
    assert c.canonicalize_entity("a inteligência artificial") == "INTELIGÊNCIA ARTIFICIAL"
    assert c.canonicalize_entity("the algorithm") == "ALGORITMO"
    assert c.canonicalize_entity("Os dados") == "DADOS"


def test_hyphen_and_underscore_form_same_lookup_key():
    # #041: clean_string dobra hífen/underscore para espaço.
    c = SemanticCanonicalizer()
    assert c.clean_string("conecta-se a") == "conecta se a"
    assert c.canonicalize_entity("rede-neural") == "REDES NEURAIS"
    assert c.canonicalize_entity("redes_neurais_artificiais") == "REDES NEURAIS"


def test_folded_dictionary_has_no_conflicting_collisions():
    # Reconstrução com chaves foldadas no __init__ não pode mapear para valores distintos.
    c = SemanticCanonicalizer()
    assert c.entity_synonyms["inteligencia artificial"] == "INTELIGÊNCIA ARTIFICIAL"
    assert c.entity_synonyms["visao computacional"] == "VISÃO COMPUTACIONAL"
    assert c.predicate_synonyms["contem"] == "CONTIENE"
    assert c.predicate_synonyms["e"] == "SER"
    assert c.predicate_synonyms["usa se"] == "UTILIZA"


def test_empty_entity_resolves_to_empty():
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("") == ""
    assert c.canonicalize_entity("   ") == ""
    assert c.clean_string("") == ""
