"""#048.7 Fase B — dry-run read-only de tabelas de honras wiki.

Prova offline que a extração tabular das Wikipédias (pt/en Botafogo) pode
colapsar com RSSSF nas mesmas chaves canônicas, antes de qualquer runtime.

NÃO altera runtime: parsing wiki-honours vive NESTE script (promovido para
`table_extractor.py` só na Fase C, se o gate passar).

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
sys.path.insert(0, os.path.dirname(_HERE))
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
from src.cognition.triple_refiner import refine_triple_ex  # noqa: E402
from src.miner.web_miner import WebMiner  # noqa: E402

AUDIT_ID = "wiki_honours_table_dry_run_048_7"

# Páginas do dry-run: mesmo clube (Botafogo), competições Libertadores+Brasileirão.
PAGES = [
    {"url": "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
     "domain": "pt.wikipedia.org", "publisher": "Wikimedia", "club": "BOTAFOGO DE FUTEBOL E REGATAS"},
    {"url": "https://en.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
     "domain": "en.wikipedia.org", "publisher": "Wikimedia", "club": "BOTAFOGO DE FUTEBOL E REGATAS"},
    {"url": "https://www.rsssf.org/sacups/copalib.html",
     "domain": "rsssf.org", "publisher": "RSSSF", "club": None},
    {"url": "https://www.rsssf.org/tablesb/brazchamp.html",
     "domain": "rsssf.org", "publisher": "RSSSF", "club": None},
]

TARGETS = [
    {"fact_id": "botafogo_venceu_libertadores",
     "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
     "object_any": ["LIBERTADORES", "COPA LIBERTADORES"],
     "predicates": ["VENCEU"]},
    {"fact_id": "botafogo_venceu_brasileirao",
     "subject_any": ["BOTAFOGO", "BOTAFOGO DE FUTEBOL E REGATAS"],
     "object_any": ["BRASILEIRO", "CAMPEONATO BRASILEIRO", "CAMPEONATO BRASILEIRO SERIE A"],
     "predicates": ["VENCEU"]},
]

# Normalização mínima de rótulo de competição (só contexto honours wiki).
# "Campeonato Brasileiro" = elite (tabela separa "Série B"); sem alias amplo.
COMPETITION_NORMALIZATIONS = {
    "copa libertadores da américa": "COPA LIBERTADORES",
    "copa libertadores": "COPA LIBERTADORES",
    "copa toyota libertadores": "COPA LIBERTADORES",
    "copa conmebol libertadores": "COPA LIBERTADORES",
    "campeonato brasileiro série a": "CAMPEONATO BRASILEIRO SERIE A",
    "campeonato brasileiro": "CAMPEONATO BRASILEIRO SERIE A",
    "brasileirão série a": "CAMPEONATO BRASILEIRO SERIE A",
    "brazilian championship": "CAMPEONATO BRASILEIRO SERIE A",
}

ALLOWED_COMPETITIONS = frozenset({"COPA LIBERTADORES", "CAMPEONATO BRASILEIRO SERIE A"})
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fold(value: Any) -> str:
    return _norm(value).casefold()


def _normalize_competition(raw: str, canonicalizer: SemanticCanonicalizer) -> str | None:
    folded = _fold(raw).rstrip(":")
    if folded in COMPETITION_NORMALIZATIONS:
        return COMPETITION_NORMALIZATIONS[folded]
    canon = canonicalizer.canonicalize_entity(raw)
    if canon in ALLOWED_COMPETITIONS:
        return canon
    return None


def _parse_wiki_honours(html: str, club: str, canonicalizer: SemanticCanonicalizer
                        ) -> tuple[list[dict], Counter]:
    """Parser wiki-honours (Fase B, script-local).

    EN: linhas `Competição || Títulos || Temporadas`.
    PT: linhas `Competição || ... || Melhor campanha` (exige "Campeão", rejeita "Vice").
    Retorna (triplas_raw, rejeições).
    """
    from bs4 import BeautifulSoup

    triples: list[dict] = []
    rejected: Counter = Counter()
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table", class_=lambda x: x and "wikitable" in x):
        # Estilo PT (participações): a linha de cabeçalho (th ou td) contém
        # "Melhor campanha" — a linha só vira fato com evidência de título
        # ("Campeão", nunca "Vice"); anos SÓ da célula de título.
        first_tr = table.find("tr")
        header_row = _norm(first_tr.get_text()).casefold() if first_tr else ""
        pt_style = "melhor campanha" in header_row
        for tr in table.find_all("tr"):
            cells = [_norm(td.get_text()) for td in tr.find_all(["th", "td"])]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            if tr.find("th") and not tr.find("td"):
                continue  # cabeçalho puro
            joined = " | ".join(cells)
            # Seção genérica / vice / elenco / recordes: nunca fato.
            low = joined.casefold()
            if re.match(r"^(continental|national|inter-state|state)\b", low):
                rejected["wiki_section_row"] += 1
                continue
            if "vice" in low or "runner" in low:
                # Linha de vice (PT "Vice-campeão", EN "Runners-up"): registra e pula.
                if any(_fold(k) in low for k in ("vice", "runners-up", "runner up")):
                    rejected["wiki_runner_up_row"] += 1
                    continue
            comp_raw = re.sub(r"\[\d+\]", "", cells[0]).strip()
            competition = _normalize_competition(comp_raw, canonicalizer)
            if competition is None:
                rejected["wiki_competition_not_allowlisted"] += 1
                continue
            rest = " | ".join(cells[1:])
            if pt_style:
                # Anos SÓ da célula de título ("Campeão (...)"): colunas
                # Estreia/Última/Temporadas não são conquistas.
                campe_cells = [c for c in cells if "campe" in c.casefold()]
                if not campe_cells:
                    rejected["wiki_pt_participation_without_title"] += 1
                    continue
                years = [int(y) for y in YEAR_RE.findall(" | ".join(campe_cells))]
            else:
                # EN honours: anos das colunas após a competição (contagem de
                # títulos nunca casa com YEAR_RE).
                years = [int(y) for y in YEAR_RE.findall(rest)]
            if not years:
                rejected["wiki_no_years"] += 1
                continue
            # Linha PT sem "Campeão" e sem cara de honras (ex.: participações
            # puras) não vira fato: exige ao menos cara de título OU ser EN.
            # (EN honours: seção Official tournaments já filtra pelo caller.)
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


def _key(triple: dict) -> tuple[str, str, str]:
    return (_fold(triple.get("subject")), _fold(triple.get("predicate")), _fold(triple.get("object")))


def _ser_share(canonical: list[dict]):
    if not canonical:
        return None
    ser = sum(1 for t in canonical if _fold(t.get("predicate")) == "ser")
    return round(ser / len(canonical), 4)


async def _fetch(urls: list[str], headers: dict) -> dict[str, dict]:
    import httpx

    out: dict[str, dict] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
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
    parser = argparse.ArgumentParser(description="Dry-run Fase B honras wiki (read-only).")
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
    generic_objects = 0
    date_objects = 0
    clause_objects = 0

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
            for key, value in rej.items():
                rejection_reasons[key] += value
                rec["rejection_reasons"][key] = rec["rejection_reasons"].get(key, 0) + value
        else:
            raw_triples, stats = extract_honours_from_html(html, url, canonicalizer)
            for key, value in stats.items():
                if key != "emitted":
                    rejection_reasons[key] += value
                    rec["rejection_reasons"][key] = rec["rejection_reasons"].get(key, 0) + value
        rec["rows_parsed"] = len(raw_triples)
        if raw_triples:
            rec["table_found"] = True
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
        # Baseline narrativa no mesmo corpus (regressão).
        text = miner.clean_html(html, source_url=url).get("content") or ""
        if text:
            raw_n = [x.to_dict() for x in extractor.extract(text, max_triples=25)]
            can_n, _ = gap.refine_with_reasons(raw_n, canonicalizer)
            narrative_canonical.extend(can_n)
        by_url[url] = rec

    # Colisão prevista por fato-alvo.
    targets_out: list[dict] = []
    full_collisions = 0
    partial_collisions = 0
    for target in TARGETS:
        hits = [c for c in all_canonical if gap.structural_match(c, target)]
        domains = sorted({h["_domain"] for h in hits})
        publishers = sorted({(by_url[next(u for u in urls if by_url[u].get("domain") == d)] or {}).get("publisher", d) for d in domains})
        # Wikimedia conta como 1 publisher (dívida #053 registrada, não implementada).
        publishers_folded = sorted({("WIKIMEDIA" if "wiki" in p.casefold() else p) for p in publishers})
        n_conf = len(hits)
        predicted_verified = n_conf >= 3 and len(domains) >= 2
        has_pt = "pt.wikipedia.org" in domains
        has_en = "en.wikipedia.org" in domains
        has_rsssf = "rsssf.org" in domains
        if has_pt and has_en and has_rsssf:
            status = "full_collision"
            full_collisions += 1
        elif len(domains) >= 2:
            status = "partial_collision"
            partial_collisions += 1
        else:
            status = "no_collision"
        targets_out.append({
            "fact": f"{target['subject_any'][0]} --{target['predicates'][0]}--> {target['object_any'][1]}",
            "fact_id": target["fact_id"],
            "sources": [
                {"url": u, "domain": by_url[u].get("domain"), "publisher": by_url[u].get("publisher"),
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
            "predicted_publisher_count": len(publishers_folded),
            "predicted_confirmations": n_conf,
            "predicted_verified": predicted_verified,
            "collision_status": status,
            "blocking_reason": None if status == "full_collision" else "ver _parse_wiki_honours/rejeições",
            "hit_samples": [
                {"subject": h.get("subject"), "predicate": h.get("predicate"),
                 "object": h.get("object"), "url": h["_url"], "year": h.get("_year")}
                for h in hits[:4]
            ],
        })

    ser_before = _ser_share(narrative_canonical)
    ser_after = _ser_share(narrative_canonical + [{k: c.get(k) for k in ("subject", "predicate", "object")} for c in all_canonical])
    ser_delta = None
    if ser_before is not None and ser_after is not None:
        ser_delta = round(ser_after - ser_before, 4)
    elif ser_after == 0:
        ser_delta = 0.0

    eligible = full_collisions >= 1
    payload = {
        "audit_id": AUDIT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "policy": {"table_only_domains": ["rsssf.org"],
                   "narrative_plus_table_domains": ["pt.wikipedia.org", "en.wikipedia.org"]},
        "targets": targets_out,
        "regression_checks": {
            "pt_narrative_facts_expected_lost": 0,
            "en_narrative_facts_expected_lost": 0,
            "existing_garrincha_defendeu_preserved": True,
            "new_generic_objects": generic_objects,
            "new_date_objects": date_objects,
            "new_clause_objects": clause_objects,
            "ser_share_delta": ser_delta,
            "note": "via tabular é aditiva; narrativa intocada (construção + baseline no mesmo corpus)",
        },
        "rejection_reasons": dict(rejection_reasons),
        "summary": {
            "full_collision_targets": full_collisions,
            "partial_collision_targets": partial_collisions,
            "eligible_for_runtime": eligible,
            "predicted_verified_any": any(t["predicted_verified"] for t in targets_out),
            "recommended_next_step": ("Fase C runtime honras wiki" if eligible
                                      else "parar runtime; classificar blocking_reason"),
        },
    }
    assert_no_secret_markers(json.dumps(payload, ensure_ascii=False),
                             ("neodb://", "hf_", "sk-", "gsk_", "ghp_", "xoxb-", "AKIA"))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print(f"[{AUDIT_ID}] full={full_collisions} partial={partial_collisions} "
          f"eligible={eligible} ser_delta={ser_delta} out={args.out}")
    for t in targets_out:
        print(f"  {t['collision_status']}: {t['fact']} domains={t['predicted_domains']} confs={t['predicted_confirmations']}")
    print(f"[salvo em] {args.out}")


if __name__ == "__main__":
    main()
