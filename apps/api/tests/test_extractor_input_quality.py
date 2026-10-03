"""#058.11.1 (F3) — qualidade de input: fragmentos não-oracionais são
rejeitados antes da extração.

Invariantes do filtro:
- determinístico (regex/contagem, sem spaCy, sem LLM);
- não altera a regra de root VERB/AUX de ``extract_spacy``;
- conservador: frases nominais/copulares legítimas (combustível do F1
  #058.11.2) devem sobreviver ao F3.
"""
from __future__ import annotations

import pytest

from src.cognition.extractor import (
    EntityExtractor,
    classify_sentence_candidate,
    is_propositional_sentence,
)
from src.miner.source_productivity import (
    analyze_text,
    split_sentences,
    split_sentences_with_stats,
)
from src.miner.web_miner import WebMiner

REJECTED_JUNK = [
    # tokens de menos de 3 / numérico puro / pontuação
    "Botafogo",
    "Pelé",
    "1962",
    "[1]",
    "24–0",
    "Editar",
    # títulos e blocos de wiki
    "Botafogo de Futebol e Regatas – Wikipédia, a enciclopédia livre",
    "Pelé - Wikipedia Pelé ONM OMC Informações pessoais Nome completo",
    # legendas / UI / referências
    "Image source, Getty Images Image caption, Pelé em 1970",
    "Share close panel Live Reporting Report (active) Scores",
    "Retrieved 12 January 2020",
    "See also References External links",
    # linhas de tabela / placar / infobox
    "Maracanã Stadium, 1950-2007",
    "J G A Abril Mateo Ponte LD Botafogo 3 1 0 Maio",
    "São Paulo Thiago Carpini 18 de abril Flamengo 2–1 São Paulo",
    "2016 ) ​ Children 7, including Edinho",
]

GOOD_F1_FUEL = [
    # verbal: passa fácil
    "The club was founded in 1904.",
    "Botafogo is based in Rio de Janeiro.",
    "The stadium holds 46,831 spectators.",
    "Pelé played for Santos FC.",
    "O Botafogo conquistou seu terceiro título nacional em 1968.",
    "Pelé defendeu o Santos durante toda a sua carreira.",
    "O estádio fica localizado no bairro da Vila Belmiro.",
    "Garrincha também é pai de um filho sueco.",
    # nominal/copular: combustível do F1 — NÃO pode ser bloqueado aqui
    "Estádio Urbano Caldeira, also known as Vila Belmiro.",
    "Botafogo de Futebol e Regatas, founded in 1904.",
    "Founded in 1904, the club joined the league two years later.",
    "The team's home ground is the Estádio Olímpico Nilton Santos.",
    "O Santos FC e um clube brasileiro fundado em 1912.",
    "A torcida do Santos e considerada a segunda maior do Brasil.",
]


@pytest.mark.parametrize("text", REJECTED_JUNK)
def test_junk_candidates_are_rejected(text: str) -> None:
    assert classify_sentence_candidate(text) is not None
    assert is_propositional_sentence(text) is False


@pytest.mark.parametrize("text", GOOD_F1_FUEL)
def test_nominal_and_verbal_sentences_survive_f3(text: str) -> None:
    assert is_propositional_sentence(text) is True


def test_rejection_reasons_use_the_documented_buckets() -> None:
    assert classify_sentence_candidate("Botafogo") == "too_short"
    assert classify_sentence_candidate("Image source, Getty Images") == "noise_marker"
    assert classify_sentence_candidate("Wikipédia, a enciclopédia livre") == "noise_marker"
    assert (
        classify_sentence_candidate("Maracanã Stadium capacity 1950 2007")
        == "non_propositional_fragment"
    )


def test_split_sentences_filters_junk_and_reports_rejection_buckets() -> None:
    text = (
        "O Santos venceu o Vasco na final. "
        "Botafogo de Futebol e Regatas – Wikipédia, a enciclopédia livre. "
        "1962. "
        "[1] Editar. "
        "Image source, Getty Images Image caption. "
        "Pelé defendeu o Santos durante toda a sua carreira."
    )
    kept, stats = split_sentences_with_stats(text)
    assert kept == [
        "O Santos venceu o Vasco na final.",
        "Pelé defendeu o Santos durante toda a sua carreira.",
    ]
    assert stats["noise_marker"] == 2
    assert stats["too_short"] == 2
    assert stats["non_propositional_fragment"] == 0
    assert split_sentences(text) == kept


def test_analyze_text_exposes_pre_filter_rejections() -> None:
    text = (
        "Botafogo de Futebol e Regatas – Wikipédia, a enciclopédia livre. "
        "Maracanã Stadium capacity 1950 2007. "
        "Pelé defendeu o Santos durante toda a sua carreira."
    )
    report = analyze_text(text, url="https://example.com/x")
    pre = report["pre_filter_rejections"]
    assert set(pre) >= {"too_short", "noise_marker", "non_propositional_fragment"}
    assert pre["noise_marker"] >= 1
    assert pre["non_propositional_fragment"] >= 1
    assert report["sentences_considered"] == 1


def test_extract_spacy_skips_junk_candidates_even_with_verb() -> None:
    extractor = EntityExtractor(enable_fallback=True)
    if extractor._nlp is None:
        pytest.skip("spaCy indisponível")
    triples = extractor.extract_spacy(
        "Pelé - Wikipedia jogou pelo Santos. O Santos venceu o Vasco em 1962.",
        max_triples=50,
    )
    joined = [f"{t.subject} {t.object}" for t in triples]
    assert all("Wikipedia" not in term for term in joined)


def test_clean_html_strips_infobox_and_figure_captions() -> None:
    html = """
    <html><head><title>Pelé</title></head><body>
      <table class="infobox">
        <tr><th>Informações pessoais</th></tr>
        <tr><td>Nome completo: Edson Arantes do Nascimento</td></tr>
      </table>
      <figure><img src="x.jpg"/><figcaption>Image caption, Pelé em 1970</figcaption></figure>
      <p>O Santos venceu o Vasco na final da Copa.</p>
    </body></html>
    """
    result = WebMiner().clean_html(html, source_url="https://pt.wikipedia.org/wiki/Pel%C3%A9")
    content = result["content"]
    assert "venceu o Vasco" in content
    assert "Informações pessoais" not in content
    assert "Image caption" not in content
