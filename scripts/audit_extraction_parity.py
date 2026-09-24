"""#058.3 — Cross-lingual extraction parity audit (read-only).

Investiga por que alvos PT/EN do cluster de futebol não convergem na mesma
tripla canônica. Prioridade: fallback demo-memory → extração → refino → alias.

Não altera Neo4j/Qdrant, não chama o endpoint de ingestão, não faz reset, não
promove fato, não altera quórum. Saída:
``reports/extraction_parity_pt_en_YYYY-MM-DD.json``.
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
except ImportError:
    pass

from src.cognition.extraction_parity_audit import (  # noqa: E402
    analyze_source_run,
    build_parity_report,
    classify_log_fallback,
    domain_of,
    parse_worker_ingest_log,
)

DEFAULT_TARGETS: dict[str, dict[str, str]] = {
    "santos_fc": {
        "canonical_entity": "SANTOS FUTEBOL CLUBE",
        "pt": "https://pt.wikipedia.org/wiki/Santos_FC",
        "en": "https://en.wikipedia.org/wiki/Santos_FC",
    },
    "pele": {
        "canonical_entity": "EDSON ARANTES DO NASCIMENTO",
        "pt": "https://pt.wikipedia.org/wiki/Pel%C3%A9",
        "en": "https://en.wikipedia.org/wiki/Pel%C3%A9",
    },
    "garrincha": {
        "canonical_entity": "MANUEL FRANCISCO DOS SANTOS",
        "pt": "https://pt.wikipedia.org/wiki/Garrincha",
        "en": "https://en.wikipedia.org/wiki/Garrincha",
    },
    "estadio_urbano_caldeira": {
        "canonical_entity": "ESTÁDIO URBANO CALDEIRA",
        "pt": "https://pt.wikipedia.org/wiki/Est%C3%A1dio_Urbano_Caldeira",
        "en": "https://en.wikipedia.org/wiki/Vila_Belmiro",
    },
    "botafogo": {
        "canonical_entity": "BOTAFOGO DE FUTEBOL E REGATAS",
        "pt": "https://pt.wikipedia.org/wiki/Botafogo_de_Futebol_e_Regatas",
        "en": "https://en.wikipedia.org/wiki/Botafogo_F.C._%28Rio_de_Janeiro%29",
    },
    "sao_paulo": {
        "canonical_entity": "SAO PAULO",
        "pt": "https://pt.wikipedia.org/wiki/S%C3%A3o_Paulo",
        "en": "https://en.wikipedia.org/wiki/S%C3%A3o_Paulo",
    },
}

# Marcadores de escrita proibidos (montados para não triparem o self-check).
READ_ONLY_CYPHER_MARKERS = (
    "MER" + "GE",
    "CRE" + "ATE",
    "SE" + "T ",
    "DELE" + "TE",
    "REMOV" + "E",
    "DRO" + "P",
    "DETACH " + "DELETE",
    "api/" + "ingest",
    "persist_" + "episodes",
)


def assert_read_only_source(source: str) -> None:
    """Falha se o script chamar APIs de escrita (AST), sem caçar strings de docstring."""
    tree = ast.parse(source)
    forbidden_attrs = {"ingest", "persist_episodes", "upsert", "detach_delete"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.lower() in forbidden_attrs:
                raise ValueError(f"read-only violado: chamada .{node.func.attr}")


def _strip_html(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_log_entries(log_path: Path) -> dict[str, dict[str, Any]]:
    if not log_path.exists():
        return {}
    raw = log_path.read_bytes()
    text = ""
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "latin-1"):
        try:
            text = raw.decode(encoding)
            if "Resposta" in text or "telemetria" in text or "partial_success" in text:
                break
        except UnicodeDecodeError:
            continue
    else:
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            return {}
    return parse_worker_ingest_log(text)


async def load_graph_facts_by_url() -> dict[str, list[dict[str, Any]]]:
    """Read-only: fatos persistidos agrupados pela URL de FonteWeb."""
    if not os.environ.get("NEO4J_URI"):
        return {}
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    out: dict[str, list[dict[str, Any]]] = {}
    query = """
    MATCH (fw:FonteWeb)-[:CONFIRMA]->(f:Fato)
    RETURN fw.url AS url,
           coalesce(f.sujeito, f.subject) AS subject,
           coalesce(f.predicado, f.predicate) AS predicate,
           coalesce(f.objeto, f.object) AS object,
           coalesce(f.fact_hash, f.hash, '') AS fact_hash
    """
    try:
        async with driver.session() as session:
            async for rec in await session.run(query):
                url = rec["url"] or ""
                if not url:
                    continue
                out.setdefault(url, []).append(
                    {
                        "subject": rec["subject"],
                        "predicate": rec["predicate"],
                        "object": rec["object"],
                        "fact_hash": rec["fact_hash"],
                        "url": url,
                        "domains": [domain_of(url)],
                    }
                )
    finally:
        await driver.close()
    return out


def dry_run_extract(url: str, *, timeout: float = 45.0) -> dict[str, Any]:
    """Dry-run offline de fetch + extração (sem chamada de ingestão, sem grafo)."""
    import httpx

    from src.miner.source_productivity import analyze_text

    headers = {"User-Agent": "Nexus-Alpha-Research/1.0 (read-only audit #058.3)"}
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        plain = _strip_html(resp.text)
        report = analyze_text(plain, url=str(resp.url), status=resp.status_code)
        return {
            "url": url,
            "final_url": str(resp.url),
            "domain": domain_of(str(resp.url)),
            "fetch_status": resp.status_code,
            "cleaned_text_length": report.get("cleaned_text_length", len(plain)),
            "sentences_considered": report.get("sentences_considered", 0),
            "raw_triples": report.get("raw_triples", 0),
            "canonical_triples": report.get("canonical_triples", 0),
            "rejected_reasons": report.get("rejection_reasons") or {},
            "quality": report.get("extractive_quality", ""),
            "notes": report.get("notes", ""),
            "canonical_facts": [
                {
                    "subject": s,
                    "predicate": p,
                    "object": o,
                    "url": str(resp.url),
                    "domains": [domain_of(str(resp.url))],
                }
                for s, p, o in _top_triples(report)
            ],
            "fetch_error": "",
        }
    except Exception as exc:
        return {
            "url": url,
            "final_url": "",
            "domain": domain_of(url),
            "fetch_status": 0,
            "cleaned_text_length": 0,
            "sentences_considered": 0,
            "raw_triples": 0,
            "canonical_triples": 0,
            "rejected_reasons": {},
            "quality": "unproductive",
            "notes": f"fetch falhou: {type(exc).__name__}",
            "canonical_facts": [],
            "fetch_error": str(exc),
        }


def _top_triples(report: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Pares sujeito/objeto top não dão tripla completa — reextraímos se necessário.

    ``analyze_text`` expõe top_*; para paridade preferimos re-extrair triplas
    canônicas reais. Como o report não lista triplas, devolvemos lista vazia e o
    chamador usa ``dry_run_extract_triples``.
    """
    return []


def dry_run_extract_triples(url: str, *, timeout: float = 45.0) -> dict[str, Any]:
    """Dry-run com triplas canônicas reais (extract + refine), read-only."""
    import httpx

    from src.cognition.extractor import EntityExtractor
    from src.cognition.triple_refiner import refine_triple_ex

    headers = {"User-Agent": "Nexus-Alpha-Research/1.0 (read-only audit #058.3)"}
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    except Exception as exc:
        return {
            "url": url,
            "final_url": "",
            "domain": domain_of(url),
            "fetch_status": 0,
            "cleaned_text_length": 0,
            "sentences_considered": 0,
            "raw_triples": 0,
            "canonical_triples": 0,
            "rejected_reasons": {},
            "quality": "unproductive",
            "notes": f"fetch falhou: {type(exc).__name__}",
            "canonical_facts": [],
            "fetch_error": str(exc),
        }

    plain = _strip_html(resp.text)
    extractor = EntityExtractor(enable_fallback=True)
    raw = extractor.extract(plain)
    facts: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for triple in raw:
        data = triple.to_dict() if hasattr(triple, "to_dict") else dict(triple)
        refined, reason = refine_triple_ex(data)
        if refined is None:
            key = str(reason or "unknown")
            rejected[key] = rejected.get(key, 0) + 1
            continue
        final_url = str(resp.url)
        facts.append(
            {
                "subject": refined.get("subject"),
                "predicate": refined.get("predicate"),
                "object": refined.get("object"),
                "raw_subject": data.get("subject"),
                "raw_predicate": data.get("predicate"),
                "raw_object": data.get("object"),
                "url": final_url,
                "domains": [domain_of(final_url)],
            }
        )

    return {
        "url": url,
        "final_url": str(resp.url),
        "domain": domain_of(str(resp.url)),
        "fetch_status": resp.status_code,
        "cleaned_text_length": len(plain),
        "sentences_considered": max(1, plain.count(".") + plain.count("!") + plain.count("?")),
        "raw_triples": len(raw),
        "canonical_triples": len(facts),
        "rejected_reasons": rejected,
        "quality": "productive" if len(facts) >= 3 else ("weak" if facts else "unproductive"),
        "notes": "",
        "canonical_facts": facts,
        "fetch_error": "",
    }


def build_source_from_graph_and_log(
    *,
    url: str,
    graph_facts: list[dict[str, Any]],
    log_entry: Optional[dict[str, Any]],
    dry: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    log_entry = log_entry or {}
    fallback = classify_log_fallback(log_entry) if log_entry else {
        "fallback_used": False,
        "fallback_type": "",
        "fallback_written_to_graph": False,
    }
    # Prefer dry-run para contagens de camada; grafo para persistidos.
    base = dry or {}
    canonical_from_graph = list(graph_facts or [])
    canonical_count = int(
        base.get("canonical_triples")
        if base.get("canonical_triples") is not None
        else len(canonical_from_graph)
    )
    # Se o grafo tem fatos da URL, usa-os como evidência de persistência.
    if canonical_from_graph:
        facts_for_hash = canonical_from_graph
        if not base.get("canonical_facts"):
            canonical_count = max(canonical_count, len(canonical_from_graph))
    else:
        facts_for_hash = list(base.get("canonical_facts") or [])

    return analyze_source_run(
        url=url,
        domain=domain_of(url),
        fetch_status=int(base.get("fetch_status") or log_entry.get("fetch_status") or 200),
        final_url=str(base.get("final_url") or url),
        cleaned_text_length=int(base.get("cleaned_text_length") or 0),
        sentences_considered=int(base.get("sentences_considered") or 0),
        raw_triples=int(base.get("raw_triples") if base.get("raw_triples") is not None else (log_entry.get("raw_triples") or 0)),
        canonical_triples=canonical_count,
        rejected_reasons=base.get("rejected_reasons") or {},
        canonical_facts=facts_for_hash,
        fallback_used=bool(fallback.get("fallback_used")),
        fallback_type=str(fallback.get("fallback_type") or ""),
        fallback_written_to_graph=bool(fallback.get("fallback_written_to_graph")),
        entities_processed=log_entry.get("entities_processed"),
        db_status=str(log_entry.get("db_status") or ""),
        ingest_status=str(log_entry.get("ingest_status") or ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Paridade extração PT/EN (#058.3, read-only)")
    parser.add_argument(
        "--log",
        default=str(Path("reports/worker_run_35942830764.log")),
        help="Log do worker (UTF-8/UTF-16)",
    )
    parser.add_argument("--worker-run-id", default="35942830764")
    parser.add_argument("--build-space-commit", default="5eb6931")
    parser.add_argument("--quorum", type=int, default=int(os.environ.get("NEXUS_VERIFY_QUORUM", "3")))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch offline das URLs (sem endpoint de ingestão, sem grafo)",
    )
    parser.add_argument("--no-graph", action="store_true", help="Não consultar Neo4j")
    parser.add_argument(
        "--out",
        default="",
        help="Caminho do relatório (default reports/extraction_parity_pt_en_YYYY-MM-DD.json)",
    )
    args = parser.parse_args()

    # Guard read-only do próprio script.
    source = Path(__file__).read_text(encoding="utf-8")
    assert_read_only_source(source)

    log_entries = load_log_entries(Path(args.log))
    graph_by_url: dict[str, list[dict[str, Any]]] = {}
    if not args.no_graph:
        graph_by_url = asyncio.run(load_graph_facts_by_url())

    targets: list[dict[str, Any]] = []
    for name, spec in DEFAULT_TARGETS.items():
        sources = {}
        for lang in ("pt", "en"):
            url = spec[lang]
            # match log keys tolerando encoding
            log_entry = log_entries.get(url)
            if log_entry is None:
                for key, value in log_entries.items():
                    if key.rstrip("/").lower() == url.rstrip("/").lower():
                        log_entry = value
                        break
            graph_facts = graph_by_url.get(url) or graph_by_url.get(url.rstrip("/")) or []
            dry = None
            if args.dry_run:
                dry = dry_run_extract_triples(url)
            sources[f"{lang}_source"] = build_source_from_graph_and_log(
                url=url,
                graph_facts=graph_facts,
                log_entry=log_entry,
                dry=dry,
            )
        targets.append(
            {
                "target": name.replace("_", " ").title(),
                "canonical_entity": spec["canonical_entity"],
                **sources,
            }
        )

    report = build_parity_report(
        targets,
        build_space_commit=args.build_space_commit,
        worker_run_id=args.worker_run_id,
        quorum=args.quorum,
    )

    # Fallback summary a partir do log (prioridade #063 vs #058.4).
    fallback_rows = [classify_log_fallback(e) for e in log_entries.values()]
    report["fallback_log_analysis"] = {
        "entries": len(fallback_rows),
        "fallback_used": sum(1 for r in fallback_rows if r["fallback_used"]),
        "fallback_written_to_graph": sum(
            1 for r in fallback_rows if r["fallback_written_to_graph"]
        ),
        "masked_extraction_failure": sum(
            1 for r in fallback_rows if r["masked_extraction_failure"]
        ),
        "urls": [
            r for r in fallback_rows if r["fallback_used"] or r["masked_extraction_failure"]
        ],
        "priority": (
            "high_#063"
            if any(r["fallback_written_to_graph"] for r in fallback_rows)
            else (
                "high_#058.4"
                if any(r["masked_extraction_failure"] for r in fallback_rows)
                else "low"
            )
        ),
    }
    report["sources_analyzed"] = sum(len(t["sources"]) for t in report["targets"])

    out = Path(
        args.out
        or f"reports/extraction_parity_pt_en_{datetime.now(timezone.utc):%Y-%m-%d}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n[salvo em] {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
