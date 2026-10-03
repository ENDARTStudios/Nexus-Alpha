"""#059E - testes dos atlases read-only (DISPUTOU + GEO). Sem rede."""
from __future__ import annotations

from pathlib import Path

import scripts.audit_geo_localizado_osm as geo
import scripts.audit_disputou_participation_atlas as disp

ROOT = Path(__file__).resolve().parent.parent


# --- DISPUTOU ---------------------------------------------------------------


def test_disputou_accepts_explicit_participant_list():
    html = "<p>O Botafogo de Futebol e Regatas disputou a Copa Libertadores em 2024.</p>"
    rec = disp.scan_text(html, domain="pt.wikipedia.org", source_type="wiki_narrative", url="x")
    assert any(f["club"] == "BOTAFOGO DE FUTEBOL E REGATAS" for f in rec["facts"])
    assert any(f["competition"] == "COPA LIBERTADORES" for f in rec["facts"])
    assert all(f["evidence"] == "explicit_participant" for f in rec["facts"])


def test_disputou_rejects_year_as_object():
    # Sem clube+competicao+verbo: nenhum fato; ano nunca vira objeto.
    html = "<p>Campeonato 2024 grupo A rodada 34 1o lugar 79 pontos.</p>"
    rec = disp.scan_text(html, domain="rsssf.org", source_type="rsssf_participation", url="x")
    assert rec["facts"] == []


def test_disputou_rejects_round_position_points_result():
    for junk in ("oitavas de final", "posicao 4", "79 pontos", "venceu por 2x1"):
        html = f"<p>Botafogo {junk} 2024</p>"
        rec = disp.scan_text(html, domain="rsssf.org", source_type="rsssf_participation", url="x")
        # sem competicao allowlisted + verbo de participacao -> nenhum fato
        assert rec["facts"] == []


def test_disputou_rejects_pronoun_subject():
    html = "<p>O time disputou a Copa Libertadores em 2023.</p>"
    rec = disp.scan_text(html, domain="pt.wikipedia.org", source_type="wiki_narrative", url="x")
    assert rec["facts"] == []


def test_disputou_rejects_ambiguous_homonym():
    html = "<p>Botafogo-PB disputou a Copa Libertadores em 2020.</p>"
    rec = disp.scan_text(html, domain="pt.wikipedia.org", source_type="wiki_narrative", url="x")
    assert all(f["club"] != "BOTAFOGO DE FUTEBOL E REGATAS" for f in rec["facts"])


# --- GEO --------------------------------------------------------------------


def test_geo_accepts_clean_addr_city():
    assert geo.nominatim_city({"city": "Santos"}) == "SANTOS"
    assert geo.nominatim_city({"city": "Rio de Janeiro"}) == "RIO DE JANEIRO"


def test_geo_rejects_neighborhood_as_city():
    assert geo.match_city("Vila Belmiro") is None
    assert geo.match_city("Engenho de Dentro") is None


def test_geo_rejects_full_address_as_city():
    assert geo.match_city("Rua Princesa Isabel, 123, Vila Belmiro") is None


def test_geo_wiki_clean_city_only():
    assert geo.wiki_city("O estadio esta localizado na cidade do Rio de Janeiro.") == "RIO DE JANEIRO"
    assert geo.wiki_city("The stadium is located in the neighborhood of Engenho de Dentro.") is None


# --- Invariantes: nenhum atlas escreve em Neo4j/Qdrant ----------------------


def test_atlas_scripts_do_not_touch_graph_or_vector():
    for name in ("scripts/audit_geo_localizado_osm.py", "scripts/audit_disputou_participation_atlas.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert "from src.database" not in source
        assert "get_graph_connector(" not in source
        assert "get_vector_connector(" not in source
        assert "import neo4j" not in source
        assert "QdrantClient" not in source
        assert '"/api/ingest"' not in source
