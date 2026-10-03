"""Testes do sanitizador de logs e do interceptor de requisições."""
from __future__ import annotations

from src.security.interceptor import RequestInterceptor
from src.security.log_sanitizer import sanitize_text


def test_sanitize_masks_bolt_password():
    out = sanitize_text("Falha ao conectar: bolt://neo4j:S3nh4Fake@neo4j-db:7687")
    assert "S3nh4Fake" not in out
    assert "[MASKED]" in out


def test_sanitize_masks_neo4j_s_uri():
    out = sanitize_text("neo4j+s://user:supersecret@abc.databases.neo4j.io")
    assert "supersecret" not in out


def test_sanitize_masks_bearer_and_nexus_token():
    out = sanitize_text("Authorization: Bearer abcdef1234567890 X-Nexus-Token: topsecretvalue")
    assert "abcdef1234567890" not in out
    assert "topsecretvalue" not in out


def test_sanitize_non_string_is_returned_as_is():
    assert sanitize_text(None) is None  # type: ignore[arg-type]


def test_interceptor_rejects_oversized_payload():
    interceptor = RequestInterceptor(max_bytes=100)
    assert interceptor.check_size(50) is True
    assert interceptor.check_size(101) is False
    assert interceptor.check_size(None) is True


def test_interceptor_brute_force_block():
    interceptor = RequestInterceptor()
    assert interceptor.block_brute("1.2.3.4", attempts=3) is False
    assert interceptor.block_brute("1.2.3.4", attempts=11) is True
