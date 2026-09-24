"""#058.8 — Banda sparse: merge lazy do fallback regex sob spaCy.

Propriedade de segurança: o fix só altera a banda 1..9 de triplas spaCy.
`spaCy==0` (fallback puro verbatim) e `spaCy>=SPACY_SPARSE_MIN` (retorno
verbatim, fallback nunca invocado) são bit-a-bit idênticos ao comportamento
anterior. Sem dependência de modelo spaCy instalado (monkeypatch).
"""
from __future__ import annotations

import pytest

from src.cognition.extractor import EntityExtractor, Triple


def _t(subject: str, predicate: str, obj: str) -> Triple:
    return Triple(subject=subject, predicate=predicate, object=obj, confidence=0.5)


def _make(
    monkeypatch: pytest.MonkeyPatch,
    *,
    spacy_triples: list[Triple],
    fallback_triples: list[Triple],
    enable_fallback: bool = True,
) -> tuple[EntityExtractor, dict]:
    extractor = EntityExtractor(enable_fallback=enable_fallback)
    calls = {"spacy": 0, "fallback": 0}

    def fake_spacy(text: str, max_triples: int = 25) -> list[Triple]:
        calls["spacy"] += 1
        return spacy_triples

    def fake_fallback(text: str, max_triples: int = 10) -> list[Triple]:
        calls["fallback"] += 1
        return fallback_triples if len(fallback_triples) <= max_triples else fallback_triples[:max_triples]

    monkeypatch.setattr(extractor, "extract_spacy", fake_spacy)
    monkeypatch.setattr(extractor, "extract_fallback", fake_fallback)
    return extractor, calls


def test_sparse_band_merges_fallback_first_then_spacy_only(monkeypatch):
    spacy_only = _t("Entidade Nova", "FOI", "So no spaCy")
    extractor, calls = _make(
        monkeypatch,
        spacy_triples=[_t("Sujeito", "POSSUIR", "Objeto")],
        fallback_triples=[_t("Fallback A", "UTILIZA", "X"), _t("Fallback B", "SER", "Y")],
    )
    merged = extractor.extract("texto")
    assert calls["fallback"] == 1, "banda sparse deve invocar o fallback"
    assert [t.subject for t in merged] == ["Fallback A", "Fallback B", "Sujeito"]
    assert spacy_only not in merged


def test_dense_band_returns_spacy_verbatim_and_never_calls_fallback(monkeypatch):
    dense = [_t(f"S{i}", "SER", f"O{i}") for i in range(EntityExtractor.SPACY_SPARSE_MIN)]
    extractor, calls = _make(
        monkeypatch,
        spacy_triples=dense,
        fallback_triples=[_t("Nunca", "SER", "Deve")],
    )
    result = extractor.extract("texto")
    assert result is dense, "retorno denso deve ser verbatim (sem cópia/cap novo)"
    assert calls["fallback"] == 0, "regex fallback não pode ser invocado no denso"


def test_boundary_9_triggers_merge(monkeypatch):
    spacy9 = [_t(f"S{i}", "SER", f"O{i}") for i in range(9)]
    extractor, calls = _make(
        monkeypatch,
        spacy_triples=spacy9,
        fallback_triples=[_t("FB", "SER", "FBO")],
    )
    merged = extractor.extract("texto")
    assert calls["fallback"] == 1, "9 < 10 deve disparar o merge"
    assert len(merged) == 10


def test_boundary_10_does_not_trigger_merge(monkeypatch):
    spacy10 = [_t(f"S{i}", "SER", f"O{i}") for i in range(10)]
    extractor, calls = _make(monkeypatch, spacy_triples=spacy10, fallback_triples=[])
    extractor.extract("texto")
    assert calls["fallback"] == 0, "10 não é < 10 — merge não dispara"


def test_zero_spacy_returns_fallback_verbatim(monkeypatch):
    fallback = [_t("Fallback Puro", "UTILIZA", "Dado")]
    extractor, calls = _make(monkeypatch, spacy_triples=[], fallback_triples=fallback)
    result = extractor.extract("texto")
    assert result is fallback, "banda 0 deve devolver o fallback verbatim (inalterado)"
    assert calls["fallback"] == 1


def test_zero_spacy_fallback_disabled_returns_empty(monkeypatch):
    extractor, calls = _make(
        monkeypatch, spacy_triples=[], fallback_triples=[_t("X", "SER", "Y")],
        enable_fallback=False,
    )
    assert extractor.extract("texto") == []
    assert calls["fallback"] == 0


def test_dedupe_casefold_covers_subject_predicate_object(monkeypatch):
    extractor, _ = _make(
        monkeypatch,
        spacy_triples=[_t("pelé", "jogou", "santos")],
        fallback_triples=[_t("Pelé", "Jogou", "Santos"), _t("Outro", "SER", "Algo")],
    )
    merged = extractor.extract("texto")
    subjects = [t.subject for t in merged]
    assert subjects == ["Pelé", "Outro"], "casefold nos 3 campos deve colapsar a duplicata"


def test_merged_respects_max_triples(monkeypatch):
    fallback = [_t(f"FB{i}", "SER", f"FO{i}") for i in range(5)]
    spacy = [_t(f"SP{i}", "SER", f"SO{i}") for i in range(5)]
    extractor, _ = _make(monkeypatch, spacy_triples=spacy, fallback_triples=fallback)
    merged = extractor.extract("texto", max_triples=7)
    assert len(merged) == 7
    assert [t.subject for t in merged[:5]] == [f"FB{i}" for i in range(5)], (
        "fallback primeiro: o cap corta o spaCy, não o regex"
    )


def test_spacy_sparse_min_constant_is_ten():
    assert EntityExtractor.SPACY_SPARSE_MIN == 10


def test_real_fallback_path_without_spacy_unchanged():
    """_nlp ausente (CI lite/local): extract() = fallback, como antes do #058.8."""
    extractor = EntityExtractor(enable_fallback=True)
    if extractor._nlp is not None:
        pytest.skip("spaCy instalado — banda 0 coberta pelo monkeypatch acima")
    text = "Inteligência Artificial utiliza Redes Neurais."
    assert extractor.extract(text) == extractor.extract_fallback(text, max_triples=25)
