"""Testes do modelo de reputação de domínio (#056) — determinístico, sem rede."""
from __future__ import annotations

from src.miner.security_protocol import SecurityProtocol, REPUTABLE_PUBLISHERS


def test_reputable_publishers_are_not_quarantined():
    proto = SecurityProtocol()
    for url in (
        "https://almanaquedosclubes.com/clubes/santos",
        "https://www.santosfc.com.br/institucional/historia",
        "https://www.cbf.com.br/",
        "https://www.fifa.com/",
        "https://ge.globo.com/futebol/",
        "https://www.lance.com.br/",
    ):
        assert proto.domain_score(url) == 0.85, url
        assert proto.confidence(url, "texto declarativo normal") >= proto.min_domain_score, url


def test_reputable_matches_registrable_suffix():
    proto = SecurityProtocol()
    assert proto.domain_score("https://ge.globo.com/futebol") == 0.85
    assert proto.domain_score("https://globoesporte.globo.com/x") == 0.85
    assert proto.domain_score("https://www.espn.com.br/x") == 0.85


def test_high_trust_and_tech_unchanged():
    proto = SecurityProtocol()
    assert proto.domain_score("https://pt.wikipedia.org/wiki/Santos_FC") == 0.9
    assert proto.domain_score("https://pytorch.org") == 0.9
    assert proto.domain_score("https://huggingface.co/docs") == 0.8
    assert proto.domain_score("https://openai.com/research") == 0.8


def test_unknown_and_low_trust_still_blocked():
    proto = SecurityProtocol()
    assert proto.domain_score("https://example.com") == 0.6
    assert proto.domain_score("https://reddit.com/x") == 0.4
    assert proto.confidence("https://example.com", "texto normal") < proto.min_domain_score
    assert proto.confidence("https://reddit.com/x", "texto normal") < proto.min_domain_score


def test_reputable_list_has_no_secrets_or_social():
    joined = " ".join(REPUTABLE_PUBLISHERS).lower()
    for forbidden in ("twitter.com", "x.com", "facebook.com", "instagram.com",
                      "tiktok.com", "youtube.com", "reddit.com", "medium.com"):
        assert forbidden not in joined
    for secret in ("token", "password", "secret", "hf_"):
        assert secret not in joined
