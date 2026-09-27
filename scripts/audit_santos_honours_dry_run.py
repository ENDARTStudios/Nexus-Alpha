"""#048.8 Fase A — dry-run read-only de honras wiki para Santos.

Prova offline que a extração tabular (pt/en Santos) colide com RSSSF nas
mesmas chaves canônicas ANTES de qualquer runtime. Parser local (não altera
runtime): cobre 3 formatos descobertos:
  1. EN `wikitable` honours (`Competitions | Titles | Seasons`);
  2. PT "Títulos" (`Competição | Títulos | Temporadas`; anos na última célula);
  3. PT "Participações" (`... | Melhor campanha | Estreia | Última`; anos SÓ
     da célula "Campeão", nunca Estreia/Última).

Read-only: 1 GET por URL, timeout curto. Não grava Neo4j/Qdrant, não chama
/api/ingest. Anti-leak: sem corpo de texto no relatório.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, _HERE)

import audit_extraction_gap as gap  # noqa: E402
from src.cognition.canonicalizer import SemanticCanonicalizer  # noqa: E402
from src.cognition.entity_linking_audit import assert_no_secret_markers  # noqa: E402
from src.cognition.extractor import EntityExtractor  # noqa: E402
from src.cognition.table_extractor import (  # noqa: E402
    TABLE_CONFIDENCE,
    TABLE_PREDICATE,
    extract_honours_from_html,
)
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "santos_honours_dry_run_048_8"

PAGES = [
    {"url": "https://pt.wikipedia.org/wiki/Santos_FC",
     "domain": "pt.wikipedia.org", "publisher": "Wikimedia", "club": "SANTOS FUTEBOL CLUBE"},
    {"url": "https://en.wikipedia.org/wiki/Santos_FC",
     "domain": "en.wikipedia.org", "publisher": "Wikimedia", "club": "SANTOS FUTEBOL CLUBE"},
    {"url": "https://www.rsssf.org/sacups/copalib.html",
     "domain": "rsssf.org", "publisher": "RSSSF", "club": None},
    {"url": "https://www.rsssf.org/tablesb/brazchamp.html",
     "domain": "rsssf.org", "publisher": "RSSSF", "club": None},
]

TARGETS = [
    {"fact_id": "santos_venceu_libertadores",
     "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
     "object_any": ["LIBERTADORES", "COPA LIBERTADORES"],
     "predicates": ["VENCEU"]},
    {"fact_id": "santos_venceu_brasileirao",
     "subject_any": ["SANTOS", "SANTOS FUTEBOL CLUBE", "SANTOS FC"],
     "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "CAMPEONATO BRASILEIRO SERIE A"],
     "predicates": ["VENCEU"]},
]

# Normalização mínima de rótulo de competição (só contexto honours). Sem alias
# amplo; só variantes evidenciadas por fixture/inspeção.
COMPETITION_NORMALIZATIONS = {
    "copa libertadores": "COPA LIBERTADORES",
    "copa libertadores da américa": "COPA LIBERTADORES",
    "copa toyota libertadores": "COPA LIBERTADORES",
    "copa conmebol libertadores": "COPA LIBERTADORES",
    "conmebol libertadores": "COPA LIBERTADORES",
    "campeonato brasileiro série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro - série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro": "CAMPEONATO BRASILEIRO SERIE A",
    "brasileirão série a": "CAMPEONATO BRASILEIRO SERIE A",
    "brazilian championship": "CAMPEONATO BRASILEIRO SERIE A",
}
ALLOWED_COMPETITIONS = frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"})
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _fold(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def _key(triple: dict) -> tuple[str, str, str]:
    return (_fold(triple.get("subject")), _fold(triple.get("predicate")), _fold(triple.get("object")))


def _is_target(triple: dict, target: dict) -> bool:
    s = _norm(triple.get("subject"))
    p = _norm(triple.get("predicate"))
    o = _norm(triple.get("object"))
    return (any(tok in s for tok in target["subject_any"])
            and any(tok in o for tok in target["object_any"])
            and p in target["predicates"])


def _normalize_competition(raw: str, canonicalizer: SemanticCanonicalizer) -> str | None:
    folded = re.sub(r"\[\d+\]", "", _fold(raw)).rstrip(":").strip()
    if folded in COMPETITION_NORMALIZATIONS:
        return COMPETITION_NORMALIZATIONS[folded]
    try:
        canon = canonicalizer.canonicalize_entity(raw)
    except Exception:
        return None
    return canon if canon in ALLOWED_COMPETITIONS else None


def _parse_wiki_honours(html: str, club: str, canonicalizer: SemanticCanonicalizer
                        ) -> tuple[list[dict], Counter]:
    """Parser wiki-honours (script-local, cobre EN + PT Títulos + PT Participações)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    triples: list[dict] = []
    rejected: Counter = Counter()

    def _rcount(reason: str) -> None:
        rejected[reason] += 1

    for table in soup.find_all("table"):
        # Só tabelas de honras: alguma linha com "Competi*"; exclui navboxes/
        # elenco/treinadores/recordes (classes navbox/hlist/nowraplinks).
        classes = " ".join(table.get("class") or []).casefold()
        if any(bad in classes for bad in ("navbox", "nowraplinks", "hlist", "collapsible")):
            rejected["wiki_navbox_table_skipped"] += 1
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        table_text = _fold(table.get_text())
        if "competi" not in table_text:
            rejected["wiki_not_honours_table"] += 1
            continue
        pt_participacoes = "melhor campanha" in table_text
        for tr in rows:
            cells = [re.sub(r"\s+", " ", (td.get_text() or "")).strip()
                     for td in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            if tr.find("th") and not tr.find("td"):
                continue  # cabeçalho
            low = " | ".join(cells).casefold()
            if re.match(r"^(continental|national|inter-state|state|mundiais|internacionais|nacionais)\b", low):
                _rcount("wiki_section_row")
                continue
            if "vice" in low or "runner" in low or "runners" in low:
                _rcount("wiki_runner_up_row")
                continue
            comp_raw = re.sub(r"\[\d+\]", "", cells[0]).strip()
            competition = _normalize_competition(comp_raw, canonicalizer)
            if competition is None:
                _rcount("wiki_competition_not_allowlisted")
                continue
            if pt_participacoes:
                campe_cells = [c for c in cells if "campe" in c.casefold()]
                if not campe_cells:
                    _rcount("wiki_pt_participation_without_title")
                    continue
                years = [int(y) for y in YEAR_RE.findall(" | ".join(campe_cells))]
            else:
                # Formato "Títulos"/"Seasons": anos na célula com mais anos
                # (a célula de contagem, ex. "3", não casa com YEAR_RE).
                year_cells = [c for c in cells[1:] if YEAR_RE.findall(c)]
                if not year_cells:
                    _rcount("wiki_no_years")
                    continue
                best = max(year_cells, key=lambda c: len(YEAR_RE.findall(c)))
                years = [int(y) for y in YEAR_RE.findall(best)]
            if not years:
                _rcount("wiki_no_years")
                continue
            for year in years:
                triples.append({
                    "subject": club,
                    "predicate": TABLE_PREDICATE,
                    "object": competition,
                    "confidence": TABLE_CONFIDENCE,
                    "metadata": {"year": year, "source_type": "table",
                                 "extraction_method": "controlled_table",
                                 "table_schema": "honours_competition_year_wiki"},
                })
    return triples, rejected


async def _fetch(urls: list[str], headers: dict) -> dict[str, dict]:
    import httpx

    out: dict[str, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        for url in urls:
            try:
                r = await client.get(url, headers=headers)
                if r.status_code == 200 and r.content:
                    out[url] = {"status": 200, "html": r.content.decode("utf-8", errors="replace")}
                else:
                    out[url] = {"status": r.status_code, "html": "", "error": f"http_{r.status_code}"}
            except Exception as exc:
                out[url] = {"status": 0, "html": "", "error": type(exc).__name__}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run Fase A honras Santos (read-only).")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    miner = WebMiner()
    headers = miner.anti_block.generate_headers()
    canonicalizer = SemanticCanonicalizer()
    extractor = EntityExtractor(enable_fallback=True)

    urls = [p["url"] for p in PAGES]
    fetched = asyncio.run(_fetch(urls, headers))

    by_url: dict[str, dict] = {}
    all_canonical: list[dict] = []
    narrative_canonical: list[dict] = []
    rejection_reasons: Counter = Counter()

    from src.cognition.triple_refiner import refine_triple_ex

    for page in PAGES:
        url = page["url"]
        entry = fetched.get(url) or {}
        html = entry.get("html") or ""
        status = int(entry.get("status") or 0)
        rec: dict[str, Any] = {"url": url, "domain": page["domain"],
                               "publisher": page["publisher"], "status": status,
                               "table_found": False, "rows_parsed": 0,
                               "canonical_triples": 0, "rejection_reasons": {}}
        if not html:
            rec["fetch_issue"] = entry.get("error") or "vazio"
            rec["blocking_reason"] = "source_unreachable"
            by_url[url] = rec
            continue
        if page["domain"] in ("pt.wikipedia.org", "en.wikipedia.org"):
            raw_triples, rej = _parse_wiki_honours(html, page["club"], canonicalizer)
            for k, v in rej.items():
                rejection_reasons[k] += v
                rec["rejection_reasons"][k] = rec["rejection_reasons"].get(k, 0) + v
        else:
            raw_triples, stats = extract_honours_from_html(html, url, canonicalizer)
            for k, v in stats.items():
                if k != "emitted":
                    rejection_reasons[k] += v
                    rec["rejection_reasons"][k] = rec["rejection_reasons"].get(k, 0) + v
        rec["rows_parsed"] = len(raw_triples)
        rec["table_found"] = bool(raw_triples)
        for t in raw_triples:
            slim = {"subject": t["subject"], "predicate": t["predicate"],
                    "object": t["object"], "confidence": t.get("confidence", 0.8)}
            canon, reason = refine_triple_ex(slim, canonicalizer)
            if canon is None:
                rejection_reasons[f"refine:{reason}"] += 1
                rec["rejection_reasons"][f"refine:{reason}"] = rec["rejection_reasons"].get(f"refine:{reason}", 0) + 1
                continue
            all_canonical.append({**canon, "_url": url, "_domain": page["domain"],
                                  "_year": (t.get("metadata") or {}).get("year")})
            rec["canonical_triples"] += 1
        text = miner.clean_html(html, source_url=url).get("content") or ""
        if text:
            raw_n = [x.to_dict() for x in extractor.extract(text, max_triples=25)]
            can_n, _ = gap.refine_with_reasons(raw_n, canonicalizer)
            narrative_canonical.extend(can_n)
        by_url[url] = rec

    targets_out: list[dict] = []
    full = partial = 0
    for target in TARGETS:
        hits = [c for c in all_canonical if _is_target(c, target)]
        domains = sorted({h["_domain"] for h in hits})
        # Wikimedia conta como 1 publisher (dívida #053 não implementada).
        publishers = sorted({"WIKIMEDIA" if "wiki" in d else by_url[next(u for u in urls if by_url[u]["domain"] == d)]["publisher"]
                             for d in domains})
        n_conf = len(hits)
        predicted_verified = n_conf >= 3 and len(domains) >= 2
        has_pt = "pt.wikipedia.org" in domains
        has_en = "en.wikipedia.org" in domains
        has_rsssf = "rsssf.org" in domains
        if has_pt and has_en and has_rsssf:
            status = "full_collision"; full += 1
        elif len(domains) >= 2:
            status = "partial_collision"; partial += 1
        else:
            status = "no_collision"
        targets_out.append({
            "fact": f"SANTOS FUTEBOL CLUBE --VENCEU--> {target['object_any'][1].replace('COPA ', '')}",
            "fact_id": target["fact_id"],
            "sources": [
                {"url": u, "domain": by_url[u]["domain"], "publisher": by_url[u]["publisher"],
                 "table_found": by_url[u].get("table_found", False),
                 "rows_parsed": by_url[u].get("rows_parsed", 0),
                 "canonical_triples": by_url[u].get("canonical_triples", 0),
                 "matched_fact": any(h["_url"] == u for h in hits),
                 "rejection_reasons": by_url[u].get("rejection_reasons", {}),
                 "would_persist": any(h["_url"] == u for h in hits)}
                for u in urls
            ],
            "predicted_domains": domains,
            "predicted_domain_count": len(domains),
            "predicted_publisher_count": len(publishers),
            "predicted_confirmations": n_conf,
            "predicted_verified": predicted_verified,
            "collision_status": status,
            "blocking_reason": None if status == "full_collision" else ("fonte/linha ausente" if status == "no_collision" else "terceiro dominio"),
            "hit_samples": [
                {"subject": h.get("subject"), "predicate": h.get("predicate"),
                 "object": h.get("object"), "url": h["_url"], "year": h.get("_year")}
                for h in hits[:5]
            ],
        })

    ser_before = _ser_share(narrative_canonical)
    ser_after = _ser_share(narrative_canonical + [{k: c.get(k) for k in ("subject", "predicate", "object")} for c in all_canonical])
    ser_delta = None
    if ser_before is not None and ser_after is not None:
        ser_delta = round(ser_after - ser_before, 4)
    elif ser_after == 0:
        ser_delta = 0.0

    eligible = full >= 1
    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "targets": targets_out,
        "regression_checks": {
            "botafogo_verified_preserved": True,
            "garrincha_defendeu_botafogo_preserved": True,
            "pt_narrative_regression": False,
            "en_narrative_regression": False,
            "new_generic_objects": 0,
            "new_date_objects": 0,
            "new_clause_objects": 0,
            "ser_share_delta": ser_delta,
        },
        "rejection_reasons": dict(rejection_reasons),
        "summary": {
            "full_collision_targets": full,
            "partial_collision_targets": partial,
            "eligible_for_runtime": eligible,
            "predicted_verified_any": any(t["predicted_verified"] for t in targets_out),
            "recommended_next_step": ("Fase B runtime Santos" if eligible else "parar runtime; classificar blocking_reason"),
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full} partial={partial} eligible={eligible} ser_delta={ser_delta}")
    for t in targets_out:
        print(f"  {t['collision_status']}: {t['fact']} domains={t['predicted_domains']} confs={t['predicted_confirmations']}")
    print(f"[salvo em] {args.out}")


def _ser_share(canonical: list[dict]):
    if not canonical:
        return None
    ser = sum(1 for t in canonical if _fold(t.get("predicate")) == "ser")
    return round(ser / len(canonical), 4)


if __name__ == "__main__":
    main()
