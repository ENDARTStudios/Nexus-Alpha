"""Inspeção 2 — Colapso cross-lingual PT vs EN (read-only).

1) Extrai do Neo4j fatos confirmados por pt.wikipedia / en.wikipedia.
2) Re-extrai offline as páginas-alvo e roda refine_triple_ex.
3) Compara chaves canônicas e decompõe divergência campo-a-campo.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    # CI lite (requirements-dev.txt) não inclui python-dotenv; o script
    # pure (fact_key/classify) precisa importar sem a dependência opcional.
    pass

TARGETS = {
    "santos_fc": {
        "pt": "https://pt.wikipedia.org/wiki/Santos_FC",
        "en": "https://en.wikipedia.org/wiki/Santos_FC",
    },
    "estadio_urbano_caldeira": {
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
        "en": "https://en.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
    },
    "pele": {
        "pt": "https://pt.wikipedia.org/wiki/Pel%C3%A9",
        "en": "https://en.wikipedia.org/wiki/Pel%C3%A9",
    },
    "garrincha": {
        "pt": "https://pt.wikipedia.org/wiki/Garrincha",
        "en": "https://en.wikipedia.org/wiki/Garrincha",
    },
    "botafogo": {
        "pt": "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        "en": "https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
    },
}


def fact_key(subject: str, predicate: str, obj: str) -> str:
    raw = f"{subject}|{predicate}|{obj}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


async def graph_side() -> dict:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    out: dict = {"facts_by_domain": {}, "cross_candidates": [], "font_urls": {}}
    try:
        async with driver.session() as session:
            # facts with sources split by wiki language
            q = """
            MATCH (f:Fato)
            OPTIONAL MATCH (fw:FonteWeb)-[:CONFIRMA]->(f)
            WITH f,
                 [u IN collect(DISTINCT fw.url) WHERE u CONTAINS 'pt.wikipedia.org'] AS pt_urls,
                 [u IN collect(DISTINCT fw.url) WHERE u CONTAINS 'en.wikipedia.org'] AS en_urls,
                 collect(DISTINCT fw.domain) AS domains
            WHERE size(pt_urls) > 0 OR size(en_urls) > 0
            RETURN coalesce(f.sujeito, f.subject) AS s,
                   coalesce(f.predicado, f.predicate) AS p,
                   coalesce(f.objeto, f.object) AS o,
                   coalesce(f.fact_hash, f.hash, '') AS h,
                   pt_urls, en_urls, domains,
                   coalesce(f.confirmacoes, 0) AS confs
            """
            rows = [r async for r in await session.run(q)]
            by_dom = {"pt_only": [], "en_only": [], "both": []}
            for r in rows:
                item = {
                    "subject": r["s"],
                    "predicate": r["p"],
                    "object": r["o"],
                    "fact_hash": r["h"],
                    "pt_urls": list(r["pt_urls"]),
                    "en_urls": list(r["en_urls"]),
                    "domains": list(r["domains"]),
                    "confirmacoes": r["confs"],
                }
                if r["pt_urls"] and r["en_urls"]:
                    by_dom["both"].append(item)
                elif r["pt_urls"]:
                    by_dom["pt_only"].append(item)
                else:
                    by_dom["en_only"].append(item)
            out["facts_by_domain"] = {
                "pt_only": by_dom["pt_only"],
                "en_only": by_dom["en_only"],
                "both": by_dom["both"],
                "counts": {k: len(v) for k, v in by_dom.items()},
            }

            # candidate pairs: same subject-ish across pt/en exclusive facts
            # (lexically near, for manual diagnosis)
            pt = by_dom["pt_only"]
            en = by_dom["en_only"]
            # naive overlap on predicate for diagnosis
            pt_by_pred = defaultdict(list)
            for f in pt:
                pt_by_pred[f["predicate"]].append(f)
            for ef in en:
                for pf in pt_by_pred.get(ef["predicate"], []):
                    # score token overlap on object/subject
                    def toks(x: str) -> set[str]:
                        return set(re.findall(r"[A-ZÀ-Ü0-9]+", (x or "").upper()))

                    inter_s = toks(pf["subject"]) & toks(ef["subject"])
                    inter_o = toks(pf["object"]) & toks(ef["object"])
                    if inter_s or inter_o:
                        out["cross_candidates"].append(
                            {
                                "predicate": pf["predicate"],
                                "pt": {k: pf[k] for k in ("subject", "predicate", "object", "fact_hash", "pt_urls")},
                                "en": {k: ef[k] for k in ("subject", "predicate", "object", "fact_hash", "en_urls")},
                                "subject_token_overlap": sorted(inter_s),
                                "object_token_overlap": sorted(inter_o),
                            }
                        )
            out["cross_candidates"] = out["cross_candidates"][:40]

            # fonte urls for targets
            q2 = """
            MATCH (fw:FonteWeb)
            WHERE fw.url CONTAINS 'wikipedia.org/wiki/'
            RETURN fw.url AS u, fw.domain AS d
            """
            out["font_urls"] = [dict(r) for r in [x async for x in await session.run(q2)]]
        return out
    finally:
        await driver.close()


def refine_offline() -> dict:
    import httpx

    from src.cognition.extractor import EntityExtractor
    from src.cognition.triple_refiner import refine_triple_ex

    extractor = EntityExtractor(enable_fallback=True)
    results: dict = {}
    headers = {"User-Agent": "Nexus-Alpha-Research/1.0 (read-only audit)"}
    for name, urls in TARGETS.items():
        entry = {"target": name, "pt": None, "en": None}
        for lang in ("pt", "en"):
            url = urls[lang]
            try:
                resp = httpx.get(url, headers=headers, timeout=45.0, follow_redirects=True)
                text = resp.text
                # strip html crudely if needed — extractor may accept html or text
                # Prefer plain text via simple tag strip
                plain = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
                plain = re.sub(r"<style[\s\S]*?</style>", " ", plain, flags=re.I)
                plain = re.sub(r"<[^>]+>", " ", plain)
                plain = re.sub(r"\s+", " ", plain)
                entities = extractor.extract(plain)
                refined = []
                for ent in entities:
                    if hasattr(ent, "get"):
                        ent_dict = dict(ent)
                    else:
                        ent_dict = {
                            "subject": getattr(ent, "subject", ""),
                            "predicate": getattr(ent, "predicate", ""),
                            "object": getattr(ent, "object", ""),
                            "confidence": getattr(ent, "confidence", 0.5),
                        }
                        if hasattr(ent, "_asdict"):
                            ent_dict.update(ent._asdict())
                    refined_obj, reason = refine_triple_ex(ent_dict)
                    raw_key = fact_key(
                        str(ent_dict.get("subject", "")),
                        str(ent_dict.get("predicate", "")),
                        str(ent_dict.get("object", "")),
                    )
                    if refined_obj:
                        can_key = fact_key(
                            str(refined_obj.get("subject", "")),
                            str(refined_obj.get("predicate", "")),
                            str(refined_obj.get("object", "")),
                        )
                        refined.append(
                            {
                                "raw": {
                                    "subject": ent_dict.get("subject"),
                                    "predicate": ent_dict.get("predicate"),
                                    "object": ent_dict.get("object"),
                                },
                                "canonical": {
                                    "subject": refined_obj.get("subject"),
                                    "predicate": refined_obj.get("predicate"),
                                    "object": refined_obj.get("object"),
                                },
                                "raw_key": raw_key,
                                "can_key": can_key,
                                "reason": reason,
                            }
                        )
                    else:
                        refined.append(
                            {
                                "raw": {
                                    "subject": ent_dict.get("subject"),
                                    "predicate": ent_dict.get("predicate"),
                                    "object": ent_dict.get("object"),
                                },
                                "canonical": None,
                                "raw_key": raw_key,
                                "can_key": None,
                                "reason": reason,
                            }
                        )
                # keep only football-related or with controlled predicates for signal
                entry[lang] = {
                    "url": url,
                    "status": resp.status_code,
                    "triples_total": len(refined),
                    "canonical_ok": sum(1 for r in refined if r["canonical"]),
                    "triples": refined,
                }
            except Exception as exc:
                entry[lang] = {"url": url, "error": str(exc)}
        results[name] = entry
    return results


def compare_offline(results: dict) -> list[dict]:
    rows = []
    for name, entry in results.items():
        pt = entry.get("pt") or {}
        en = entry.get("en") or {}
        pt_triples = pt.get("triples") or []
        en_triples = en.get("triples") or []
        pt_keys = {t["can_key"]: t for t in pt_triples if t.get("can_key")}
        en_keys = {t["can_key"]: t for t in en_triples if t.get("can_key")}
        shared = set(pt_keys) & set(en_keys)
        # for shared keys — good
        # for near-misses: same predicate, overlapping tokens
        near = []
        for pt_t in pt_triples:
            if not pt_t.get("canonical"):
                continue
            for en_t in en_triples:
                if not en_t.get("canonical"):
                    continue
                if pt_t["can_key"] == en_t["can_key"]:
                    continue
                if pt_t["canonical"]["predicate"] != en_t["canonical"]["predicate"]:
                    continue
                s_pt = set(re.findall(r"[A-ZÀ-Ü0-9]+", str(pt_t["canonical"]["subject"]).upper()))
                s_en = set(re.findall(r"[A-ZÀ-Ü0-9]+", str(en_t["canonical"]["subject"]).upper()))
                o_pt = set(re.findall(r"[A-ZÀ-Ü0-9]+", str(pt_t["canonical"]["object"]).upper()))
                o_en = set(re.findall(r"[A-ZÀ-Ü0-9]+", str(en_t["canonical"]["object"]).upper()))
                inter_s = s_pt & s_en
                inter_o = o_pt & o_en
                if inter_s or inter_o:
                    divergences = []
                    if pt_t["canonical"]["subject"] != en_t["canonical"]["subject"]:
                        divergences.append(
                            {
                                "field": "subject",
                                "pt": pt_t["canonical"]["subject"],
                                "en": en_t["canonical"]["subject"],
                                "raw_pt": pt_t["raw"]["subject"],
                                "raw_en": en_t["raw"]["subject"],
                                "overlap": sorted(inter_s),
                            }
                        )
                    if pt_t["canonical"]["predicate"] != en_t["canonical"]["predicate"]:
                        divergences.append(
                            {
                                "field": "predicate",
                                "pt": pt_t["canonical"]["predicate"],
                                "en": en_t["canonical"]["predicate"],
                                "raw_pt": pt_t["raw"]["predicate"],
                                "raw_en": en_t["raw"]["predicate"],
                                "overlap": [],
                            }
                        )
                    if pt_t["canonical"]["object"] != en_t["canonical"]["object"]:
                        divergences.append(
                            {
                                "field": "object",
                                "pt": pt_t["canonical"]["object"],
                                "en": en_t["canonical"]["object"],
                                "raw_pt": pt_t["raw"]["object"],
                                "raw_en": en_t["raw"]["object"],
                                "overlap": sorted(inter_o),
                            }
                        )
                    if divergences:
                        near.append(
                            {
                                "pt": pt_t,
                                "en": en_t,
                                "divergences": divergences,
                                "same_predicate": True,
                            }
                        )
        rows.append(
            {
                "target": name,
                "pt_status": pt.get("status"),
                "en_status": en.get("status"),
                "pt_canonical": pt.get("canonical_ok"),
                "en_canonical": en.get("canonical_ok"),
                "pt_total": pt.get("triples_total"),
                "en_total": en.get("triples_total"),
                "shared_canonical_keys": sorted(shared),
                "shared_count": len(shared),
                "near_miss_same_predicate": near[:15],
                "near_miss_count": len(near),
            }
        )
    return rows


def classify(divergences: list[dict]) -> tuple[str, str]:
    """Return (hypothesis, recommended_issue) for a divergence set."""
    fields = {d["field"] for d in divergences}
    has_pred = "predicate" in fields
    has_ent = bool(fields & {"subject", "object"})
    # H4: only invisible diffs — strings equal after normalize
    from src.cognition.canonicalizer import fold_lookup_key

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", fold_lookup_key(str(s)).strip().upper())

    only_h4 = True
    for d in divergences:
        if d["field"] == "predicate":
            if norm(d["pt"]) != norm(d["en"]):
                only_h4 = False
        else:
            if norm(d["pt"]) != norm(d["en"]):
                only_h4 = False
    if only_h4 and divergences:
        return "H4 normalização", "fix normalização"
    if has_pred and has_ent:
        return "H1+H2 alias+mapper", "#047 + #045.2"
    if has_pred:
        # same entities conceptually but predicate differs
        return "H2 mapper gap", "#045.2"
    if has_ent:
        # check if pure article/determiner noise → H3, else alias → H1
        noise = False
        for d in divergences:
            if d["field"] in ("subject", "object"):
                pt = str(d["pt"]).upper()
                en = str(d["en"]).upper()
                # strip leading articles
                pt2 = re.sub(r"^(O |A |OS |AS |THE )+", "", pt)
                en2 = re.sub(r"^(O |A |OS |AS |THE )+", "", en)
                if pt2 == en2 or pt.replace(" ", "") == en.replace(" ", ""):
                    noise = True
        if noise and all(
            # if after stripping articles they match, H3
            True
            for _ in divergences
        ):
            # distinguish: if token sets almost equal after article strip → H3
            return "H3 ruído de span (artigo/determinante)", "#058.2"
        return "H1 alias de entidade", "#047"
    return "?", "?"


def main() -> None:
    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)

    graph = asyncio.run(graph_side())
    offline = refine_offline()
    comparisons = compare_offline(offline)

    # classify near-misses
    table = []
    for row in comparisons:
        for nm in row["near_miss_same_predicate"]:
            hyp, issue = classify(nm["divergences"])
            for d in nm["divergences"]:
                table.append(
                    {
                        "target_fact": row["target"],
                        "field": d["field"],
                        "pt": d["pt"],
                        "en": d["en"],
                        "raw_pt": d["raw_pt"],
                        "raw_en": d["raw_en"],
                        "hypothesis": hyp,
                        "recommended_issue": issue,
                    }
                )

    # shared keys (success cases)
    successes = []
    for row in comparisons:
        for k in row["shared_canonical_keys"]:
            successes.append({"target": row["target"], "can_key": k})

    report = {
        "report": "inspection_2_cros lingual_collapse",
        "read_only": True,
        "graph_side": {
            "counts": graph["facts_by_domain"]["counts"],
            "both_domains_facts": graph["facts_by_domain"]["both"],
            "cross_candidates_sample": graph["cross_candidates"][:20],
            "cross_candidates_total": len(graph["cross_candidates"]),
            "wiki_font_urls": graph["font_urls"],
        },
        "offline_targets": {
            name: {
                "pt": {
                    "status": (e.get("pt") or {}).get("status"),
                    "canonical_ok": (e.get("pt") or {}).get("canonical_ok"),
                    "triples_total": (e.get("pt") or {}).get("triples_total"),
                    "sample_canonical": [
                        t["canonical"]
                        for t in ((e.get("pt") or {}).get("triples") or [])
                        if t.get("canonical")
                    ][:12],
                    "rejected_sample": [
                        {"raw": t["raw"], "reason": t["reason"]}
                        for t in ((e.get("pt") or {}).get("triples") or [])
                        if not t.get("canonical")
                    ][:8],
                },
                "en": {
                    "status": (e.get("en") or {}).get("status"),
                    "canonical_ok": (e.get("en") or {}).get("canonical_ok"),
                    "triples_total": (e.get("en") or {}).get("triples_total"),
                    "sample_canonical": [
                        t["canonical"]
                        for t in ((e.get("en") or {}).get("triples") or [])
                        if t.get("canonical")
                    ][:12],
                    "rejected_sample": [
                        {"raw": t["raw"], "reason": t["reason"]}
                        for t in ((e.get("en") or {}).get("triples") or [])
                        if not t.get("canonical")
                    ][:8],
                },
            }
            for name, e in offline.items()
        },
        "comparisons": comparisons,
        "divergence_table": table,
        "shared_canonical_successes": successes,
        "summary": {
            "targets": len(comparisons),
            "targets_with_shared_keys": sum(1 for r in comparisons if r["shared_count"] > 0),
            "near_miss_total": sum(r["near_miss_count"] for r in comparisons),
            "divergence_rows": len(table),
            "hypothesis_counts": {},
        },
    }
    for t in table:
        h = t["hypothesis"]
        report["summary"]["hypothesis_counts"][h] = report["summary"]["hypothesis_counts"].get(h, 0) + 1

    out_path = out_dir / "inspection_2_croslingual.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # print human table
    print("=== GRAPH SIDE ===")
    print("counts:", graph["facts_by_domain"]["counts"])
    print("facts confirmed by BOTH pt+en wiki:", len(graph["facts_by_domain"]["both"]))
    for f in graph["facts_by_domain"]["both"][:10]:
        print(" BOTH:", f["subject"], "--", f["predicate"], "--", f["object"], f["fact_hash"])
    print("cross candidates (same predicate, token overlap):", len(graph["cross_candidates"]))
    for c in graph["cross_candidates"][:15]:
        print(
            "  P:",
            c["predicate"],
            "| PT:",
            c["pt"]["subject"],
            "--",
            c["pt"]["object"],
            "| EN:",
            c["en"]["subject"],
            "--",
            c["en"]["object"],
            "| overlap_s:",
            c["subject_token_overlap"],
            "overlap_o:",
            c["object_token_overlap"],
        )

    print("\n=== OFFLINE RE-EXTRACT ===")
    for name, row in enumerate(comparisons):
        print(
            f"{row['target']}: pt_status={row['pt_status']} en_status={row['en_status']} "
            f"pt_can={row['pt_canonical']}/{row['pt_total']} en_can={row['en_canonical']}/{row['en_total']} "
            f"shared={row['shared_count']} near_miss={row['near_miss_count']}"
        )

    print("\n=== DIVERGENCE TABLE ===")
    if not table:
        print("(no same-predicate near-misses with field divergence)")
    for t in table:
        print(
            f"{t['target_fact']:24} {t['field']:9} PT={t['pt']!r} EN={t['en']!r} "
            f"| raw PT={t['raw_pt']!r} EN={t['raw_en']!r} | {t['hypothesis']} -> {t['recommended_issue']}"
        )

    print("\n=== SHARED KEYS (collapse worked) ===")
    for s in successes:
        print(" ", s)

    print(f"\n[salvo em] {out_path}")


if __name__ == "__main__":
    main()
