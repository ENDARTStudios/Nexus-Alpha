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

# Clubes no escopo do Almanaque (forma canônica). Outros clubes parseados são
# descartados (motivo ``club_not_allowlisted``) — sem fatos fora do escopo.
CLUB_ALLOWLIST: frozenset[str] = frozenset({
    "BOTAFOGO DE FUTEBOL E REGATAS",
    "SANTOS FUTEBOL CLUBE",
})

# Linha de vice/cabeçalho/genérica nunca vira fato.
_RUNNER_UP_RE = re.compile(r"^\s*(2nd|3rd|runner|vice|runners?.?up)\b", re.IGNORECASE)
_SCORE_RE = re.compile(r"\d+\s*[-–—x×]\s*\d+")
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
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
    """URL whitelistada para extração tabular (competição por contexto)."""
    return _lookup_competition(source_url) is not None


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
    if any(tok in folded for tok in _GENERIC_ROW_TOKENS):
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
    if competition is None:
        _count("not_whitelisted_url")
        return triples, stats

    def _canonicalize(raw: str) -> str:
        if canonicalizer is not None:
            try:
                return canonicalizer.canonicalize_entity(raw)
            except Exception:
                return raw.strip().upper()
        return raw.strip().upper()

    def _emit(club_mention: str, year: Optional[int]) -> None:
        ok, reason = _club_mention_ok(club_mention)
        if not ok:
            _count(reason)
            return
        club_canon = _canonicalize(club_mention)
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
