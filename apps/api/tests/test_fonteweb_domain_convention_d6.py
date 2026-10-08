"""D6 — convenção da propriedade de domínio em :FonteWeb.

Leitura/escrita/validações usam ``domain`` (o ``dominio`` legado não existe nos
nós — verificado por probe no grafo vivo 2026-10-07). Este teste trava a
convenção no código ativo: ingest escreve ``f.domain`` e nenhum arquivo ativo
referencia a propriedade legada.
"""
from __future__ import annotations

from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (API_ROOT / relative).read_text(encoding="utf-8")


def test_graph_connector_writes_domain_property():
    text = _read("src/database/graph_connector.py")
    assert "f.domain = $domain" in text  # ingest escreve a propriedade canônica
    assert ".dominio" not in text


def test_no_active_module_uses_legacy_dominio_property():
    import re

    # "dominio" como PALAVRA aparece em prosa pt-BR (logs/docstrings) e é legítimo;
    # o que a convenção proíbe é a PROPRIEDADE de grafo: f.dominio / $dominio etc.
    property_pattern = re.compile(r"\b(?:f|fa|ff|src|w)\.dominio\b|\$dominio\b")
    offenders = []
    for path in (API_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if property_pattern.search(text):
            offenders.append(path.name)
    assert offenders == [], f"propriedade legada `dominio` em: {offenders}"


def test_schema_reference_uses_domain_not_dominio():
    schema = _read("src/database/schema.cypher")
    assert "f.domain" in schema
    assert "f.dominio" not in schema
    assert "$dominio" not in schema
