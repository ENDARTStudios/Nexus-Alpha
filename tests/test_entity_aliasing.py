"""Testes #047 — aliasing bilíngue curado de entidades.

Colapso PT/EN no canônico do YAML, negativos (entidades distintas não colapsam),
resíduos de span e golden cross-lingual com ``fact_hash`` estável.
"""
from __future__ import annotations

from pathlib import Path

from src.brain.memory import fact_hash
from src.cognition.canonicalizer import SemanticCanonicalizer, fold_lookup_key, _load_entity_aliases
from src.cognition.triple_refiner import refine_triple_ex


ALIASES_PATH = Path(__file__).resolve().parents[1] / "src" / "cognition" / "entity_aliases.yaml"


def test_aliases_yaml_loads_without_conflict():
    aliases = _load_entity_aliases(ALIASES_PATH)
    assert aliases, "entity_aliases.yaml deve carregar aliases"
    # Nenhuma chave foldada ausente
    for key, canonical in aliases.items():
        assert key and canonical


def test_santos_fc_variants_collapse_to_curated_canonical():
    c = SemanticCanonicalizer()
    for variant in (
        "Santos FC",
        "Santos Futebol Clube",
        "Santos Football Club",
        "SFC",
        "santos fc",
        "SANTOS FC",
    ):
        assert c.canonicalize_entity(variant) == "SANTOS FUTEBOL CLUBE", variant


def test_pele_variants_collapse_to_curated_canonical():
    c = SemanticCanonicalizer()
    for variant in ("Pelé", "Pele", "Edson Arantes do Nascimento", "O Rei do Futebol"):
        assert c.canonicalize_entity(variant) == "EDSON ARANTES DO NASCIMENTO", variant


def test_garrincha_and_stadium_variants_collapse():
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("Garrincha") == "MANUEL FRANCISCO DOS SANTOS"
    assert c.canonicalize_entity("Mané Garrincha") == "MANUEL FRANCISCO DOS SANTOS"
    assert c.canonicalize_entity("Estádio Urbano Caldeira") == "ESTÁDIO URBANO CALDEIRA"
    assert c.canonicalize_entity("Vila Belmiro") == "ESTÁDIO URBANO CALDEIRA"
    assert c.canonicalize_entity("Botafogo FR") == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert c.canonicalize_entity("São Paulo") == "SAO PAULO"
    assert c.canonicalize_entity("Sao Paulo") == "SAO PAULO"


def test_distinct_entities_do_not_collapse():
    # Negativos: times distintos não podem colapsar por alias acidental.
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("Flamengo") != c.canonicalize_entity("Fluminense")
    assert c.canonicalize_entity("Santos FC") != c.canonicalize_entity("Botafogo FR")
    assert c.canonicalize_entity("Pelé") != c.canonicalize_entity("Garrincha")
    assert c.canonicalize_entity("Estádio Urbano Caldeira") != c.canonicalize_entity("São Paulo")


def test_no_residual_variant_spans_after_canonicalization():
    # Resíduos: nenhuma forma crua do YAML deve sobreviver como canônica.
    c = SemanticCanonicalizer()
    aliases = _load_entity_aliases(ALIASES_PATH)
    for entry_key, canonical in aliases.items():
        # O próprio canônico é idempotente
        assert c.canonicalize_entity(canonical) == canonical
        # Variações de caixa do próprio canônico também
        assert c.canonicalize_entity(canonical.title()) == canonical


def test_fold_lookup_key_is_deterministic_for_alias_variants():
    assert fold_lookup_key("Santos FC") == fold_lookup_key("santos  fc")
    assert fold_lookup_key("O Rei do Futebol") == fold_lookup_key("rei do futebol")
    assert fold_lookup_key("São Paulo") == fold_lookup_key("Sao Paulo")


def test_golden_cross_lingual_pair_shares_fact_hash():
    # Golden cross-lingual: PT e EN da mesma tripla refinam para a mesma chave.
    pt, reason_pt = refine_triple_ex(
        {"subject": "Pelé", "predicate": "defendeu", "object": "Santos FC"}
    )
    en, reason_en = refine_triple_ex(
        {"subject": "Pele", "predicate": "played for", "object": "Santos Football Club"}
    )
    assert reason_pt == "ok" and reason_en == "ok"
    assert pt["subject"] == en["subject"] == "EDSON ARANTES DO NASCIMENTO"
    assert pt["predicate"] == en["predicate"] == "DEFENDEU"
    assert pt["object"] == en["object"] == "SANTOS FUTEBOL CLUBE"
    assert (
        fact_hash(pt["subject"], pt["predicate"], pt["object"])
        == fact_hash(en["subject"], en["predicate"], en["object"])
    )


def test_aliases_yaml_anti_leak_no_secrets():
    # Anti-leak: YAML de aliases não pode conter segredos/tokens/URLs internas.
    # Comentários do próprio anti-leak são removidos antes da varredura.
    raw_lines = ALIASES_PATH.read_text(encoding="utf-8").splitlines()
    code_only = "\n".join(
        line.split("#", 1)[0] for line in raw_lines
    ).lower()
    for needle in (
        "hf_", "sk-", "api_key", "apikey", "password", "passwd", "secret",
        "token=", "neo4j://", "bolt://", "localhost", "127.0.0.1",
        "qdrant", "nexus_api", "authorization:", "http://", "https://",
    ):
        assert needle not in code_only, f"anti-leak: {needle!r} encontrado no YAML"
