"""#048.10L.3 — resolução source-scoped de cidade esperada por URL (sem rede)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.geo_extractor import resolve_expected_geo_city  # noqa: E402

WIKI_CASES = [
    ("https://pt.wikipedia.org/wiki/Allianz_Parque", "SÃO PAULO"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Morumbi", "SÃO PAULO"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Pacaembu", "SÃO PAULO"),
    ("https://pt.wikipedia.org/wiki/Neo_Qu%C3%ADmica_Arena", "SÃO PAULO"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_Ol%C3%ADmpico_Nilton_Santos", "RIO DE JANEIRO"),
    ("https://en.wikipedia.org/wiki/Nilton_Santos_Stadium", "RIO DE JANEIRO"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_do_Maracan%C3%A3", "RIO DE JANEIRO"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio", "PORTO ALEGRE"),
    ("https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto", "BELO HORIZONTE"),
    ("https://en.wikipedia.org/wiki/Mineir%C3%A3o", "BELO HORIZONTE"),
    ("https://pt.wikipedia.org/wiki/Arena_Fonte_Nova", "SALVADOR"),
]

NOMINATIM_CASES = [
    ("https://nominatim.openstreetmap.org/search?format=json&q=Allianz%20Parque", "SÃO PAULO"),
    ("https://nominatim.openstreetmap.org/search?format=json&q=Est%C3%A1dio%20Beira-Rio", "PORTO ALEGRE"),
    ("https://nominatim.openstreetmap.org/search?format=json&q=Est%C3%A1dio%20Mineir%C3%A3o", "BELO HORIZONTE"),
    ("https://nominatim.openstreetmap.org/search?format=json&q=Arena%20Fonte%20Nova", "SALVADOR"),
    # #048.10L.4: queries desambiguadas por cidade (seed_clusters)
    ("https://nominatim.openstreetmap.org/search?format=json&q=Est%C3%A1dio%20Beira-Rio%2C%20Porto%20Alegre", "PORTO ALEGRE"),
    ("https://nominatim.openstreetmap.org/search?format=json&q=Mineir%C3%A3o%2C%20Belo%20Horizonte", "BELO HORIZONTE"),
]


def test_expected_city_resolution_wiki():
    for url, city in WIKI_CASES:
        assert resolve_expected_geo_city(url) == city, url


def test_expected_city_resolution_nominatim():
    for url, city in NOMINATIM_CASES:
        assert resolve_expected_geo_city(url) == city, url


def test_unknown_url_is_unresolved():
    assert resolve_expected_geo_city("https://pt.wikipedia.org/wiki/Stadium_Unknown") is None
    assert resolve_expected_geo_city("https://example.com/foo") is None
    assert resolve_expected_geo_city("") is None


def test_no_cross_url_inheritance():
    beira = resolve_expected_geo_city("https://pt.wikipedia.org/wiki/Est%C3%A1dio_Beira-Rio")
    mineirao = resolve_expected_geo_city("https://pt.wikipedia.org/wiki/Est%C3%A1dio_Governador_Magalh%C3%A3es_Pinto")
    assert beira == "PORTO ALEGRE" and beira != "SÃO PAULO"
    assert mineirao == "BELO HORIZONTE" and mineirao != "RIO DE JANEIRO"
