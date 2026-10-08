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
    assert "SET f.domain = $domain" in _read("src/database/graph_connector.py")


def test_no_active_module_uses_legacy_dominio_property():
    offenders = []
    for path in (API_ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "dominio" in text:
            offenders.append(path.name)
    assert offenders == [], f"propriedade legada `dominio` em: {offenders}"


def test_schema_reference_uses_domain_not_dominio():
    schema = _read("src/database/schema.cypher")
    assert "f.domain" in schema
    assert "f.dominio" not in schema
    assert "$dominio" not in schema
