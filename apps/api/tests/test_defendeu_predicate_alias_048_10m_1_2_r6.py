"""#048.10M.1.2.R6 — alias de predicado PERTENCE_A→DEFENDEU com escopo de pares.

Causa raiz R5: as infoboxes de carreira das páginas wiki do jogador extraem
``PERTENCE_A``; o atlas/registry espera ``DEFENDEU`` — o quórum 3 fragmenta por
chave canônica (mesmo fato lógico, duas chaves). O alias só se aplica aos pares
(sujeito, objeto) do atlas; qualquer outro par mantém PERTENCE_A.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.cognition.canonicalizer import SemanticCanonicalizer


@pytest.fixture(scope="module")
def canon() -> SemanticCanonicalizer:
    return SemanticCanonicalizer()


def _predicate(canon: SemanticCanonicalizer, subject: str, predicate: str, object_: str) -> str:
    return canon.canonicalize_triplet(
        {"subject": subject, "predicate": predicate, "object": object_, "confidence": 0.9}
    )["predicate"]


# --- positivos: pares do atlas unificam em DEFENDEU ---------------------------

@pytest.mark.parametrize(
    "subject,object_",
    [
        ("Jairzinho", "Botafogo de Futebol e Regatas"),
        ("JAIRZINHO", "Botafogo"),  # case + objeto curto do atlas
        ("Romário", "Clube de Regatas Vasco da Gama"),
        ("Romário de Souza Faria", "Vasco"),
        ("Sócrates", "Sport Club Corinthians Paulista"),
        ("Carlos Alberto Torres", "Santos Futebol Clube"),
        ("Zito", "Santos FC"),
        ("Rogério Ceni", "São Paulo Futebol Clube"),
        ("Garrincha", "Botafogo de Futebol e Regatas"),
    ],
)
def test_atlas_pairs_unify_pertence_a_to_defendeu(canon: SemanticCanonicalizer, subject: str, object_: str):
    assert _predicate(canon, subject, "PERTENCE_A", object_) == "DEFENDEU"


# --- negativos: fora do escopo do atlas PERTENCE_A permanece ------------------

@pytest.mark.parametrize(
    "subject,object_",
    [
        ("Maracanã", "Flamengo"),          # estádio — nunca DEFENDEU
        ("Pelé", "Santos"),                 # fora do atlas do piloto
        ("Jairzinho", "Cruzeiro"),          # sujeito do atlas, objeto fora
        ("Rivelino", "Corinthians"),        # sujeito fora (excluído do piloto)
        ("Rivellino", "Corinthians"),
    ],
)
def test_out_of_scope_pairs_keep_pertence_a(canon: SemanticCanonicalizer, subject: str, object_: str):
    assert _predicate(canon, subject, "PERTENCE_A", object_) == "PERTENCE_A"


# --- invariantes: outros predicados e formas canônicas intocados --------------

def test_defendeu_stays_defendeu(canon: SemanticCanonicalizer):
    assert _predicate(canon, "Jairzinho", "DEFENDEU", "Botafogo de Futebol e Regatas") == "DEFENDEU"


def test_other_predicates_untouched(canon: SemanticCanonicalizer):
    assert _predicate(canon, "IA", "usa", "redes neurais") == "UTILIZA"


def test_triplet_fields_preserved(canon: SemanticCanonicalizer):
    out = canon.canonicalize_triplet(
        {"subject": "Jairzinho", "predicate": "PERTENCE_A",
         "object": "Botafogo de Futebol e Regatas", "confidence": 0.8,
         "source_url": "https://pt.wikipedia.org/wiki/Jairzinho"}
    )
    assert out["confidence"] == 0.8
    assert out["source_url"].endswith("/wiki/Jairzinho")
