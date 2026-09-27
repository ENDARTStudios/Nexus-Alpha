"""Nexus-Alpha — extração tabular controlada (#058.12).

Schema único suportado: ``honours_competition_year`` — tabelas/blocos de
honras de fontes estatísticas estáticas whitelistadas geram triplas
``CLUBE --VENCEU--> COMPETIÇÃO`` (ano como metadado, nunca como objeto).

Gates do parser (antes do refine, que continua aplicando span validator,
predicate mapper e canonicalizer sem nenhuma alteração):
1. URL precisa estar na whitelist (competição vem do contexto da página);
2. sujeito precisa canonicalizar para um clube do allowlist;
3. predicado é sempre ``VENCEU`` (nunca ``SER``);
4. objeto é sempre a competição whitelistada (nunca ano/número/genérico);
5. linhas de vice (``2nd:``), placar (``3-1``), cabeçalho e genéricas são
   descartadas com motivo contabilizado.

Read-only: este módulo não grava em Neo4j/Qdrant e não altera seeds.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from bs4 import BeautifulSoup

TABLE_SCHEMA = "honours_competition_year"
EXTRACTION_METHOD = "controlled_table"
SOURCE_TYPE = "table"
TABLE_PREDICATE = "VENCEU"
TABLE_CONFIDENCE = 0.8

# URL (substring) -> competição canônica. O contexto da página define o objeto;
# a linha só precisa trazer clube + ano.
HONOURS_URL_ALLOWLIST: dict[str, str] = {
    "rsssf.org/sacups/copalib.html": "COPA LIBERTADORES",
    "rsssf.org/tablesb/brazchamp.html": "CAMPEONATO BRASILEIRO SERIE A",
}

# #048.7/#048.8/#048.9 — honras wiki: URL (substring, minúscula e URL-decoded)
# -> (clube canônico, competições habilitadas POR CLUBE, conforme colisão
# completa no dry-run). Clubes/competições só entram com full_collision.
WIKI_HONOURS_CLUBS: dict[str, tuple[str, frozenset[str]]] = {
    "wikipedia.org/wiki/botafogo_de_futebol_e_regatas": (
        "BOTAFOGO DE FUTEBOL E REGATAS",
        frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"}),
    ),
    "wikipedia.org/wiki/santos_fc": (
        "SANTOS FUTEBOL CLUBE",
        frozenset({"COPA LIBERTADORES"}),
    ),
    # #048.9 — multi-clube (dry-run full_collision):
    "wikipedia.org/wiki/clube_de_regatas_do_flamengo": (
        "CLUBE DE REGATAS DO FLAMENGO", frozenset({"COPA LIBERTADORES"}),
    ),
    "wikipedia.org/wiki/cr_flamengo": (
        "CLUBE DE REGATAS DO FLAMENGO", frozenset({"COPA LIBERTADORES"}),
    ),
    "wikipedia.org/wiki/sociedade_esportiva_palmeiras": (
        "SOCIEDADE ESPORTIVA PALMEIRAS",
        frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"}),
    ),
    "wikipedia.org/wiki/se_palmeiras": (
        "SOCIEDADE ESPORTIVA PALMEIRAS",
        frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"}),
    ),
    "wikipedia.org/wiki/são_paulo_futebol_clube": (
        "SÃO PAULO FUTEBOL CLUBE",
        frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"}),
    ),
    "wikipedia.org/wiki/são_paulo_fc": (
        "SÃO PAULO FUTEBOL CLUBE",
        frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"}),
    ),
    "wikipedia.org/wiki/grêmio_foot-ball_porto_alegrense": (
        "GREMIO FOOT BALL PORTO ALEGRENSE", frozenset({"COPA LIBERTADORES"}),
    ),
    "wikipedia.org/wiki/grêmio_fbpa": (
        "GREMIO FOOT BALL PORTO ALEGRENSE", frozenset({"COPA LIBERTADORES"}),
    ),
    "wikipedia.org/wiki/sport_club_internacional": (
        "SPORT CLUBE INTERNACIONAL", frozenset({"COPA LIBERTADORES"}),
    ),
    "wikipedia.org/wiki/sc_internacional": (
        "SPORT CLUBE INTERNACIONAL", frozenset({"COPA LIBERTADORES"}),
    ),
}

# #048.9 — a winners-list do RSSSF (copalib.html) usa nomes curtos
# ("1981 Flamengo"). Mapa SOURCE-SCOPED (só no emit RSSSF) para o canônico.
RSSSF_WINNER_ALIASES: dict[str, str] = {
    "flamengo": "CLUBE DE REGATAS DO FLAMENGO",
    "palmeiras": "SOCIEDADE ESPORTIVA PALMEIRAS",
    "são paulo": "SÃO PAULO FUTEBOL CLUBE",
    "sao paulo": "SÃO PAULO FUTEBOL CLUBE",
    "grêmio": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "gremio": "GREMIO FOOT BALL PORTO ALEGRENSE",
    "internacional": "SPORT CLUBE INTERNACIONAL",
    "botafogo": "BOTAFOGO DE FUTEBOL E REGATAS",
    "santos": "SANTOS FUTEBOL CLUBE",
}

# Normalização mínima de rótulo de competição (só contexto honours wiki).
# "Campeonato Brasileiro" = elite (a tabela separa "Série B"); sem alias amplo.
COMPETITION_NORMALIZATIONS: dict[str, str] = {
    "copa libertadores da américa": "COPA LIBERTADORES",
    "copa libertadores": "COPA LIBERTADORES",
    "copa toyota libertadores": "COPA LIBERTADORES",
    "copa conmebol libertadores": "COPA LIBERTADORES",
    "conmebol libertadores": "COPA LIBERTADORES",
    "campeonato brasileiro série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro - série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro": "CAMPEONATO BRASILEIRO SERIE A",
    "brasileirão série a": "CAMPEONATO BRASILEIRO SERIE A",
    "brazilian championship": "CAMPEONATO BRASILEIRO SERIE A",
}

# Clubes no escopo do Almanaque (forma canônica). Outros clubes parseados são
# descartados (motivo ``club_not_allowlisted``) — sem fatos fora do escopo.
CLUB_ALLOWLIST: frozenset[str] = frozenset({
    "BOTAFOGO DE FUTEBOL E REGATAS",
    "SANTOS FUTEBOL CLUBE",
    "CLUBE DE REGATAS DO FLAMENGO",
    "SOCIEDADE ESPORTIVA PALMEIRAS",
    "SÃO PAULO FUTEBOL CLUBE",
    "GREMIO FOOT BALL PORTO ALEGRENSE",
    "SPORT CLUBE INTERNACIONAL",
})

# Linha de vice/cabeçalho/genérica nunca vira fato.
_RUNNER_UP_RE = re.compile(r"^\s*(2nd|3rd|runner|vice|runners?.?up)\b", re.IGNORECASE)
_SCORE_RE = re.compile(r"\d+\s*[-–—x×]\s*\d+")
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
# Intervalo de anos (ex.: "1981–1984") indica tabela de PARTICIPAÇÕES, não títulos.
_YEAR_RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\s*[–—-]\s*(19\d{2}|20\d{2})")
_GENERIC_ROW_TOKENS = frozenset({
    "total", "titles", "years", "competition", "season", "seasons",
    "runners-up", "runner-up", "runner", "vice", "club", "team",
    "titles:", "titles won",
})
# Linha de winners-list: ANO + nome do clube (sem placar).
_WINNERS_LINE_RE = re.compile(r"^\s*(19\d{2}|20\d{2})\s+(.+?)\s*$")


def _fold(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _strip_parenthetical(text: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*", " ", text).strip()


def _lookup_competition(source_url: str) -> Optional[str]:
    low = (source_url or "").lower()
    for fragment, competition in HONOURS_URL_ALLOWLIST.items():
        if fragment in low:
            return competition
    return None


def is_honours_url(source_url: str) -> bool:
    """URL whitelistada p/ extração controlada (RSSSF/honras wiki/jogador-clube)."""
    return (
        _lookup_competition(source_url) is not None
        or _lookup_wiki_club(source_url) is not None
        or _lookup_player_club(source_url)
    )


# #059C — terceira fonte independente (não-Wikimedia) para DEFENDEU:
# RSSSF Brasil "jogadores ... como jogador do CLUBE" (club-context player records).
PLAYER_CLUB_URL_ALLOWLIST: tuple[str, ...] = ("rsssfbrasil.com/sel/jogclub.htm",)
PLAYER_CLUB_ALLOWED_PLAYERS: frozenset[str] = frozenset({
    "GARRINCHA", "MANUEL FRANCISCO DOS SANTOS", "PELÉ", "PELE",
    "EDSON ARANTES DO NASCIMENTO", "NILTON SANTOS", "DIDI", "JAIRZINHO",
    "HELENO DE FREITAS",
})
PLAYER_CLUB_ALLOWED_CLUBS: frozenset[str] = frozenset({
    "BOTAFOGO DE FUTEBOL E REGATAS", "SANTOS FUTEBOL CLUBE",
})
_PLAYER_CLUB_RE = re.compile(
    r"([^\n()]{1,45}?)\s*\(\s*\d+\s+jogos(?:[^)]*?)como jogador d[oa]\s+([^)]+?)\)"
)


def _lookup_player_club(source_url: str) -> bool:
    low = (source_url or "").lower()
    return any(frag in low for frag in PLAYER_CLUB_URL_ALLOWLIST)


def extract_player_club_from_html(
    html: str, source_url: str, canonicalizer: Any = None
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """``JOGADOR --DEFENDEU--> CLUBE`` de fonte club-context (#059C).

    Padrão controlado ``NOME (N jogos ... como jogador do CLUBE)``, com
    allowlist de jogador e clube. Anos/períodos nunca viram objeto.
    """
    stats: dict[str, int] = {}
    triples: list[dict[str, Any]] = []
    if not _lookup_player_club(source_url):
        stats["not_whitelisted_url"] = 1
        return triples, stats

    def _canon(raw: str) -> str:
        if canonicalizer is not None:
            try:
                return canonicalizer.canonicalize_entity(raw)
            except Exception:
                return raw.strip().upper()
        return raw.strip().upper()

    soup = BeautifulSoup(html or "", "html.parser")
    full = "\n".join(p.get_text() for p in soup.find_all("pre")) or soup.get_text()
    for match in _PLAYER_CLUB_RE.finditer(full):
        player = _canon(match.group(1).strip())
        club = _canon(match.group(2).strip())
        if player not in PLAYER_CLUB_ALLOWED_PLAYERS:
            stats["player_not_allowlisted"] = stats.get("player_not_allowlisted", 0) + 1
            continue
        if club not in PLAYER_CLUB_ALLOWED_CLUBS:
            stats["club_not_allowlisted"] = stats.get("club_not_allowlisted", 0) + 1
            continue
        triples.append({
            "subject": player,
            "predicate": "DEFENDEU",
            "object": club,
            "confidence": TABLE_CONFIDENCE,
            "metadata": {
                "source_type": SOURCE_TYPE,
                "extraction_method": EXTRACTION_METHOD,
                "table_schema": "club_context_player_records",
                "source_url": source_url,
            },
        })
        stats["emitted"] = stats.get("emitted", 0) + 1
    return triples, stats


# #058.12.1 — política de extração por fonte (domínio registrável).
TABLE_ONLY_DOMAINS: frozenset[str] = frozenset({"rsssf.org"})
NARRATIVE_PLUS_TABLE_DOMAINS: frozenset[str] = frozenset({
    "pt.wikipedia.org", "en.wikipedia.org",
})

POLICY_TABLE_ONLY = "table_only"
POLICY_NARRATIVE_PLUS_TABLE = "narrative_plus_table"
POLICY_NARRATIVE_DEFAULT = "narrative_default"


def _registrable_host(source_url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(source_url or "").netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def source_policy(source_url: str) -> str:
    """Política determinística por domínio.

    - ``table_only`` (ex.: rsssf.org): narrativa suprimida; só tabular
      controlada prossegue;
    - ``narrative_plus_table`` (wikis): narrativa válida + tabular quando a
      URL estiver whitelistada;
    - ``narrative_default``: comportamento atual inalterado.
    """
    host = _registrable_host(source_url)
    if not host:
        return POLICY_NARRATIVE_DEFAULT
    if host in TABLE_ONLY_DOMAINS or any(
        host.endswith("." + d) for d in TABLE_ONLY_DOMAINS
    ):
        return POLICY_TABLE_ONLY
    if host in NARRATIVE_PLUS_TABLE_DOMAINS:
        return POLICY_NARRATIVE_PLUS_TABLE
    return POLICY_NARRATIVE_DEFAULT


def enrich_payload_with_tables(
    payload: dict[str, Any], canonicalizer: Any = None
) -> dict[str, int]:
    """Via tabular controlada dentro do path do worker (`enrich_payload`).

    Consome e remove ``payload["raw_html"]`` (preservado pelo miner só para
    URLs whitelistadas; POST segue limpo). Emite triplas slim
    ``{subject, predicate, object, confidence}`` (mesmo shape de
    ``Triple.to_dict()``) appendadas a ``extracted_entities``.

    Nunca levanta exceção: qualquer falha devolve stats com ``error`` e o
    caminho narrativo segue intacto.
    """
    stats: dict[str, int] = {
        "attempted": 0, "emitted": 0,
        "skipped_no_html": 0, "skipped_not_whitelisted": 0, "error": 0,
    }
    try:
        if not isinstance(payload, dict):
            stats["error"] += 1
            return stats
        html = payload.pop("raw_html", None)
        url = payload.get("source_url", "")
        if not html:
            stats["skipped_no_html"] += 1
            return stats
        if not is_honours_url(url):
            stats["skipped_not_whitelisted"] += 1
            return stats
        if canonicalizer is None:
            from src.cognition.canonicalizer import SemanticCanonicalizer
            canonicalizer = SemanticCanonicalizer()
        triples, _parse_stats = extract_honours_from_html(html, url, canonicalizer)
        pc_triples, _pc_stats = extract_player_club_from_html(html, url, canonicalizer)
        triples = triples + pc_triples
        stats["attempted"] += len(triples)
        entities = payload.setdefault("extracted_entities", [])
        for t in triples:
            entities.append({
                "subject": t["subject"],
                "predicate": t["predicate"],
                "object": t["object"],
                "confidence": t.get("confidence", TABLE_CONFIDENCE),
            })
            stats["emitted"] += 1
        return stats
    except Exception:
        stats["error"] += 1
        return stats


def _clean_club_mention(raw: str) -> str:
    text = _strip_parenthetical(re.sub(r"\s+", " ", raw or "").strip())
    return text.strip(" -–—:;.,")


def _club_mention_ok(mention: str) -> tuple[bool, str]:
    """Gates sintáticos da menção de clube (antes da canonicalização)."""
    if not mention or len(mention) < 3:
        return False, "club_mention_too_short"
    folded = _fold(mention)
    # Match por TOKEN (não substring): "clube"/"club" em nomes legítimos
    # (Clube de Regatas do Flamengo, São Paulo Futebol Clube, Sport Club
    # Internacional) NÃO podem ser confundidos com a linha genérica "club".
    tokens = set(folded.split())
    if tokens & _GENERIC_ROW_TOKENS or folded in _GENERIC_ROW_TOKENS:
        return False, "club_mention_generic"
    if _SCORE_RE.search(mention):
        return False, "score_line_skipped"
    if _YEAR_RE.fullmatch(mention):
        return False, "year_only_row"
    if mention.isdigit():
        return False, "numeric_row"
    return True, "ok"


def _parse_pre_winners(html: str) -> tuple[list[tuple[str, Optional[int]]], dict[str, int]]:
    """Linhas ``ANO Clube`` de blocos <pre> (estilo RSSSF).

    Retorna ``([(club_mention, year)], parse_stats)``. Pula vice/placar/
    cabeçalho com contabilidade.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, Optional[int]]] = []
    parse_stats: dict[str, int] = {}

    def _pcount(reason: str) -> None:
        parse_stats[reason] = parse_stats.get(reason, 0) + 1

    for pre in soup.find_all("pre"):
        for line in (pre.get_text() or "").splitlines():
            stripped = line.strip()
            if not stripped or len(stripped) > 160:
                continue
            if _RUNNER_UP_RE.match(stripped):
                _pcount("pre_runner_up_skipped")
                continue
            if _SCORE_RE.search(stripped):
                _pcount("pre_score_line_skipped")
                continue
            # Match lines starting with a year (19xx or 20xx) followed by team name
            match = _WINNERS_LINE_RE.match(stripped)
            if match is None:
                _pcount("pre_unmatched_line")
                continue
            year = int(match.group(1))
            mention = _clean_club_mention(match.group(2))
            if mention:
                out.append((mention, year))
    return out, parse_stats


def _parse_table_honours(html: str) -> list[tuple[str, Optional[str], list[int]]]:
    """Linhas de <table> de honras: ``(club_mention, competition_mention, years)``.

    Sujeito vem do caption/cabeçalho da tabela quando presente; senão a linha
    precisa conter clube + competição nas células.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, Optional[str], list[int]]] = []
    for table in soup.find_all("table"):
        caption = table.find("caption")
        caption_club = _clean_club_mention(caption.get_text()) if caption else ""
        # cabeçalho da tabela: ignora linhas <th>-puras
        for tr in table.find_all("tr"):
            cells = [
                re.sub(r"\s+", " ", (td.get_text() or "")).strip()
                for td in tr.find_all(["th", "td"])
            ]
            cells = [c for c in cells if c]
            if not cells:
                continue
            if tr.find("th") and not tr.find("td"):
                continue  # cabeçalho puro
            joined = " | ".join(cells)
            if _RUNNER_UP_RE.match(joined):
                continue
            years = [int(y) for y in _YEAR_RE.findall(joined)]
            # competição = célula que não é ano/número e não é o clube do caption
            comp_candidates = [
                c for c in cells
                if not _YEAR_RE.fullmatch(c.strip())
                and not c.strip().isdigit()
                and _fold(c) not in _GENERIC_ROW_TOKENS
                and _fold(c) != _fold(caption_club)
            ]
            subject = caption_club
            competition = comp_candidates[0] if comp_candidates else None
            if not subject:
                # sem caption: primeira célula não-numérica vira sujeito candidato
                non_numeric = [c for c in cells if not c.strip().isdigit() and not _YEAR_RE.fullmatch(c.strip())]
                if len(non_numeric) >= 2:
                    subject, competition = _clean_club_mention(non_numeric[0]), non_numeric[1]
                else:
                    continue
            out.append((_clean_club_mention(subject), competition, years))
    return out


def _lookup_wiki_club(source_url: str) -> Optional[tuple[str, frozenset[str]]]:
    from urllib.parse import unquote

    low = unquote(source_url or "").lower()
    for fragment, club_cfg in WIKI_HONOURS_CLUBS.items():
        if fragment in low:
            return club_cfg
    return None


def _normalize_competition(raw: str, canonicalize, allowed: frozenset[str]) -> Optional[str]:
    """Rótulo de competição -> canônica permitida POR CLUBE (honours wiki)."""
    folded = _fold(raw).rstrip(":")
    folded = re.sub(r"\[\d+\]", "", folded).strip()
    if folded in COMPETITION_NORMALIZATIONS:
        return COMPETITION_NORMALIZATIONS[folded] if COMPETITION_NORMALIZATIONS[folded] in allowed else None
    try:
        canon = canonicalize(raw)
    except Exception:
        return None
    return canon if canon in allowed else None


def _parse_wiki_honours(html: str) -> tuple[list[tuple[str, list[int]]], dict[str, int]]:
    """Linhas de honras wiki: ``[(competition_mention, years)]``.

    Cobre 3 formatos (#048.7 Botafogo + #048.8 Santos):
    - EN `wikitable`: `Competitions | Titles | Seasons`;
    - PT "Títulos": `Competição | Títulos | Temporadas` (anos na última célula,
      classe livre — não necessariamente ``wikitable``);
    - PT "Participações": exige "Campeão" (nunca "Vice"); anos SÓ da célula de
      título (Estreia/Última não são conquistas).

    Só analisa tabelas de honras (alguma célula com "Competi*"); navboxes
    (`Ligações externas`), elenco, treinadores e recordes são pulados.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[tuple[str, list[int]]] = []
    stats: dict[str, int] = {}

    def _wcount(reason: str) -> None:
        stats[reason] = stats.get(reason, 0) + 1

    for table in soup.find_all("table"):
        classes = " ".join(table.get("class") or []).casefold()
        if any(bad in classes for bad in ("navbox", "nowraplinks", "hlist", "collapsible")):
            _wcount("wiki_navbox_table_skipped")
            continue
        table_text = _fold(table.get_text())
        if "competi" not in table_text:
            _wcount("wiki_not_honours_table")
            continue
        pt_participacoes = "melhor campanha" in table_text
        for tr in table.find_all("tr"):
            cells = [
                re.sub(r"\s+", " ", (td.get_text() or "")).strip()
                for td in tr.find_all(["th", "td"])
            ]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            if tr.find("th") and not tr.find("td"):
                continue  # cabeçalho puro
            joined = " | ".join(cells)
            low = joined.casefold()
            # Seções de agrupamento (EN/PT) e vice nunca são fato.
            if re.match(
                r"^(continental|national|inter-state|state|mundiais|internacionais|nacionais)\b",
                low,
            ):
                _wcount("wiki_section_row")
                continue
            if "vice" in low or "runner" in low or "runners" in low:
                _wcount("wiki_runner_up_row")
                continue
            comp_raw = re.sub(r"\[\d+\]", "", cells[0]).strip()
            if pt_participacoes:
                campe_cells = [c for c in cells if "campe" in c.casefold()]
                if not campe_cells:
                    _wcount("wiki_pt_participation_without_title")
                    continue
                year_src = " | ".join(campe_cells)
            else:
                # Formato "Títulos"/"Seasons": anos na célula com mais anos
                # (a célula de contagem, ex. "3", não casa com _YEAR_RE).
                year_cells = [c for c in cells[1:] if _YEAR_RE.findall(c)]
                if not year_cells:
                    _wcount("wiki_no_years")
                    continue
                year_src = max(year_cells, key=lambda c: len(_YEAR_RE.findall(c)))
            # Intervalo de anos (ex.: "1981–1984") = tabela de PARTICIPAÇÕES,
            # não títulos (Flamengo PT tem ambas) → rejeita.
            if _YEAR_RANGE_RE.search(year_src):
                _wcount("wiki_year_range_participation")
                continue
            years = [int(y) for y in _YEAR_RE.findall(year_src)]
            if not years:
                _wcount("wiki_no_years")
                continue
            out.append((comp_raw, years))
    return out, stats


def extract_honours_from_html(
    html: str,
    source_url: str,
    canonicalizer: Any = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Extrai triplas ``CLUBE --VENCEU--> COMPETIÇÃO`` do HTML.

    Retorna ``(triplas, stats)``. Cada tripla é dict
    ``{subject, predicate, object, confidence, metadata}`` com subject/object
    já canonicalizados (quando ``canonicalizer`` é fornecido) e filtrados pelo
    allowlist de clubes. ``stats`` contabiliza motivos de descarte.
    """
    stats: dict[str, int] = {}
    triples: list[dict[str, Any]] = []

    def _count(reason: str) -> None:
        stats[reason] = stats.get(reason, 0) + 1

    competition = _lookup_competition(source_url)
    wiki_club = _lookup_wiki_club(source_url) if competition is None else None
    if competition is None and wiki_club is None:
        _count("not_whitelisted_url")
        return triples, stats

    def _canonicalize(raw: str) -> str:
        if canonicalizer is not None:
            try:
                return canonicalizer.canonicalize_entity(raw)
            except Exception:
                return raw.strip().upper()
        return raw.strip().upper()

    def _emit_table(subject: str, obj: str, year: Optional[int],
                    schema: str = TABLE_SCHEMA) -> None:
        metadata: dict[str, Any] = {
            "year": year,
            "source_type": SOURCE_TYPE,
            "extraction_method": EXTRACTION_METHOD,
            "table_schema": schema,
            "source_url": source_url,
        }
        triples.append({
            "subject": subject,
            "predicate": TABLE_PREDICATE,
            "object": obj,
            "confidence": TABLE_CONFIDENCE,
            "metadata": metadata,
        })
        _count("emitted")

    if wiki_club is not None:
        # Modo wiki (#048.7/#048.8): sujeito fixo da página; competição da
        # linha, restrita ao allowlist POR CLUBE (evidência de dry-run).
        club_name, club_competitions = wiki_club
        if club_name not in CLUB_ALLOWLIST:
            _count("wiki_club_not_allowlisted")
            return triples, stats
        wiki_rows, wiki_stats = _parse_wiki_honours(html or "")
        for key, value in wiki_stats.items():
            stats[key] = stats.get(key, 0) + value
        for comp_mention, years in wiki_rows:
            comp_canon = _normalize_competition(comp_mention, _canonicalize, club_competitions)
            if comp_canon is None:
                _count("wiki_competition_not_allowlisted")
                continue
            for year in years:
                _emit_table(club_name, comp_canon, year,
                            schema="honours_competition_year_wiki")
        return triples, stats

    def _emit(club_mention: str, year: Optional[int]) -> None:
        ok, reason = _club_mention_ok(club_mention)
        if not ok:
            _count(reason)
            return
        club_canon = _canonicalize(club_mention)
        if club_canon not in CLUB_ALLOWLIST:
            # #048.9: winners-list RSSSF usa nomes curtos; mapa source-scoped.
            aliased = RSSSF_WINNER_ALIASES.get(_fold(club_mention))
            if aliased:
                club_canon = aliased
        if club_canon not in CLUB_ALLOWLIST:
            _count("club_not_allowlisted")
            return
        metadata: dict[str, Any] = {
            "year": year,
            "source_type": SOURCE_TYPE,
            "extraction_method": EXTRACTION_METHOD,
            "table_schema": TABLE_SCHEMA,
            "source_url": source_url,
        }
        triples.append({
            "subject": club_canon,
            "predicate": TABLE_PREDICATE,
            "object": competition,
            "confidence": TABLE_CONFIDENCE,
            "metadata": metadata,
        })
        _count("emitted")

    pre_pairs, pre_stats = _parse_pre_winners(html or "")
    for mention, year in pre_pairs:
        _emit(mention, year)
    for key, value in pre_stats.items():
        stats[key] = stats.get(key, 0) + value

    for subject, competition_cell, years in _parse_table_honours(html or ""):
        # Linha de tabela precisa afirmar a competição explicitamente: sem
        # célula de competição, não há fato (ex.: linha "Total | 3").
        if competition_cell is None:
            _count("table_competition_missing")
            continue
        comp_canon = _canonicalize(competition_cell)
        if comp_canon != competition:
            _count("table_competition_mismatch")
            continue
        if not years:
            _emit(subject, None)
        else:
            for year in years:
                _emit(subject, year)

    return triples, stats
