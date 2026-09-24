"""Testes #047 / #047.1 — aliasing bilíngue curado de entidades.

Colapso PT/EN no canônico do YAML, bloco ``evidence`` obrigatório (#047.1),
negativos (entidades distintas nunca colapsam), resíduos de span e golden
cross-lingual com colapso de subject/object para os 4 alvos do #058.3.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from src.brain.memory import fact_hash
from src.cognition.canonicalizer import SemanticCanonicalizer, fold_lookup_key, _load_entity_aliases
from src.cognition.triple_refiner import refine_triple_ex


ALIASES_PATH = Path(__file__).resolve().parents[1] / "src" / "cognition" / "entity_aliases.yaml"


def _load_raw_aliases() -> list[dict]:
    data = yaml.safe_load(ALIASES_PATH.read_text(encoding="utf-8")) or {}
    return list(data.get("aliases") or [])


def test_aliases_yaml_loads_without_conflict():
    aliases = _load_entity_aliases(ALIASES_PATH)
    assert aliases, "entity_aliases.yaml deve carregar aliases"
    # Nenhuma chave foldada ausente
    for key, canonical in aliases.items():
        assert key and canonical


def test_every_alias_entry_carries_evidence():
    # #047.1: evidência obrigatória — parity report + reason em toda entrada.
    entries = _load_raw_aliases()
    assert entries, "YAML deve ter entradas"
    for entry in entries:
        evidence = entry.get("evidence") or {}
        assert evidence.get("parity_report"), entry.get("canonical")
        assert evidence.get("reason"), entry.get("canonical")
        assert "http://" not in str(evidence)
        assert "https://" not in str(evidence)


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
    assert c.canonicalize_entity("Manuel Francisco dos Santos") == "MANUEL FRANCISCO DOS SANTOS"
    assert c.canonicalize_entity("Mané Garrincha") == "MANUEL FRANCISCO DOS SANTOS"
    assert c.canonicalize_entity("Estádio Urbano Caldeira") == "ESTÁDIO URBANO CALDEIRA"
    assert c.canonicalize_entity("Vila Belmiro") == "ESTÁDIO URBANO CALDEIRA"
    assert c.canonicalize_entity("Vila Belmiro Stadium") == "ESTÁDIO URBANO CALDEIRA"
    assert c.canonicalize_entity("Botafogo") == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert c.canonicalize_entity("Botafogo FR") == "BOTAFOGO DE FUTEBOL E REGATAS"
    assert c.canonicalize_entity("Botafogo de Futebol e Regatas") == "BOTAFOGO DE FUTEBOL E REGATAS"


def test_sao_paulo_city_vs_club_stay_distinct():
    # #047.1: cidade e clube nunca colapsam um no outro.
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("São Paulo") == "SAO PAULO"
    assert c.canonicalize_entity("Sao Paulo") == "SAO PAULO"
    assert c.canonicalize_entity("São Paulo FC") == "SÃO PAULO FUTEBOL CLUBE"
    assert c.canonicalize_entity("Sao Paulo FC") == "SÃO PAULO FUTEBOL CLUBE"
    assert c.canonicalize_entity("São Paulo Futebol Clube") == "SÃO PAULO FUTEBOL CLUBE"
    assert (
        c.canonicalize_entity("São Paulo FC")
        != c.canonicalize_entity("São Paulo")
    )


def test_distinct_entities_do_not_collapse():
    # Negativos: entidades distintas não podem colapsar por alias acidental.
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("Flamengo") != c.canonicalize_entity("Fluminense")
    assert c.canonicalize_entity("Botafogo") != c.canonicalize_entity("Vasco")
    assert c.canonicalize_entity("São Paulo FC") != c.canonicalize_entity("Palmeiras")
    assert c.canonicalize_entity("Pelé") != c.canonicalize_entity("Garrincha")
    assert (
        c.canonicalize_entity("Estádio Urbano Caldeira")
        != c.canonicalize_entity("Maracanã")
    )
    assert c.canonicalize_entity("Santos FC") != c.canonicalize_entity("Botafogo FR")
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
    assert fold_lookup_key("Botafogo FR") == fold_lookup_key("botafogo fr")


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


def test_garrincha_cross_lingual_entity_collapse():
    # #047.1 — alvo entity_divergence: subject/object PT e EN colapsam.
    c = SemanticCanonicalizer()
    assert c.canonicalize_entity("Garrincha") == c.canonicalize_entity("Garrincha")
    assert (
        c.canonicalize_entity("Botafogo")
        == c.canonicalize_entity("Botafogo de Futebol e Regatas")
        == "BOTAFOGO DE FUTEBOL E REGATAS"
    )


def test_estadio_cross_lingual_entity_collapse():
    # #047.1 — alvo entity_divergence: Vila Belmiro ↔ Estádio Urbano Caldeira.
    c = SemanticCanonicalizer()
    assert (
        c.canonicalize_entity("Vila Belmiro")
        == c.canonicalize_entity("Estádio Urbano Caldeira")
        == c.canonicalize_entity("Estadio Urbano Caldeira")
        == "ESTÁDIO URBANO CALDEIRA"
    )


def test_botafogo_cross_lingual_entity_collapse():
    # #047.1 — alvo entity_divergence: formas curtas e longas PT/EN.
    c = SemanticCanonicalizer()
    assert (
        c.canonicalize_entity("Botafogo")
        == c.canonicalize_entity("Botafogo FR")
        == c.canonicalize_entity("Botafogo F.C.")
        == "BOTAFOGO DE FUTEBOL E REGATAS"
    )


def test_sao_paulo_club_cross_lingual_entity_collapse():
    # #047.1 — clube PT/EN colapsa; cidade permanece separada.
    c = SemanticCanonicalizer()
    assert (
        c.canonicalize_entity("São Paulo FC")
        == c.canonicalize_entity("Sao Paulo FC")
        == c.canonicalize_entity("São Paulo Futebol Clube")
        == "SÃO PAULO FUTEBOL CLUBE"
    )
    assert c.canonicalize_entity("São Paulo") == "SAO PAULO"


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
