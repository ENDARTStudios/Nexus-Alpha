"""#054.7 — scheme do Neo4j: forçamento TLS restrito ao AuraDB.

O forçamento bolt://→neo4j+s:// era exigência do AuraDB (cancelado).
Destinos self-hosted standalone exigem bolt:// (neo4j+s:// espera routing
table de cluster e quebra com "Unable to retrieve routing information").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.database.graph_connector import GraphConnector


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("NEO4J_URI", "NEO4J_URL", "NEO4J_PASSWORD", "NEXUS_NEO4J_PASSWORD", "NEXUS_VERIFY_QUORUM"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NEO4J_PASSWORD", "test-password-not-real")


def _uri_for(monkeypatch, uri: str) -> str:
    monkeypatch.setenv("NEO4J_URI", uri)
    connector = GraphConnector(config_path="config/inexistente_054_7.yaml")
    return connector.uri


def test_aura_host_still_forces_tls(monkeypatch):
    # hosts AuraDB continuam com o forçamento histórico (#017)
    assert _uri_for(monkeypatch, "bolt://85cd4c04.databases.neo4j.io:7687") == (
        "neo4j+s://85cd4c04.databases.neo4j.io:7687"
    )


def test_selfhosted_bolt_uri_is_preserved(monkeypatch):
    # destino standalone (Railway) mantém o scheme explícito do operador
    uri = "bolt://zephyr.proxy.rlwy.net:40107"
    assert _uri_for(monkeypatch, uri) == uri


def test_explicit_tls_uri_is_untouched(monkeypatch):
    uri = "neo4j+s://some-host.databases.neo4j.io"
    assert _uri_for(monkeypatch, uri) == uri
