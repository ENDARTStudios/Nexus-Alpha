"""Backup final do Neo4j Aura antes do cancelamento do serviço.

Dois modos:

  export   — exporta o grafo completo (nós + rels) e o schema (constraints,
             índices, versão) para JSON canônico. READ-ONLY no grafo de origem.
  restore  — recria o grafo a partir do JSON canônico num Neo4j alvo
             (batches UNWIND, determinístico). --keep-eid preserva _eid e o
             label temporário __TMP_EID para verificação byte-a-byte.

Env de origem (export): NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD via .env de apps/api.
D11: dotenv importado de forma lazy (dentro de main()).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TEMP_LABEL = "__TMP_EID"
BATCH_SIZE = 500


def _serialize(props: dict) -> dict:
    out = {}
    for k, v in (props or {}).items():
        if hasattr(v, "iso_format"):
            out[k] = str(v)
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def _canonical_hash(payload: dict) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _label_set_clause(labels: list[str]) -> str:
    return "SET n:" + ":".join(labels)


async def _session_with_retry(uri: str, user: str, password: str, attempts: int = 4, delay: float = 8.0):
    """Sessão com retry — Aura free tier pausa por inatividade (cold boot)."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    last_exc: Exception | None = None
    for i in range(attempts):
        try:
            async with driver.session() as session:
                await session.run("RETURN 1")
            return driver
        except Exception as exc:  # noqa: BLE001 — wake-up transitório do Aura
            last_exc = exc
            print(f"[retry {i + 1}/{attempts}] conexão falhou ({type(exc).__name__}); aguardando {delay}s")
            await asyncio.sleep(delay)
    await driver.close()
    raise RuntimeError(f"Neo4j inacessível após {attempts} tentativas: {last_exc}")


async def _export(args: argparse.Namespace) -> int:
    from dotenv import load_dotenv

    base = Path(__file__).resolve().parent.parent
    load_dotenv(base / ".env")
    load_dotenv(base / ".env.local")
    import os

    uri = os.environ["NEO4J_URI"]
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ["NEO4J_PASSWORD"]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    driver = await _session_with_retry(uri, user, password)
    nodes: list[dict] = []
    rels: list[dict] = []
    schema: dict = {}
    counts: dict = {}
    try:
        async with driver.session() as session:
            async for rec in await session.run(
                "MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props"
            ):
                nodes.append({"eid": rec["eid"], "labels": sorted(rec["labels"]), "props": _serialize(rec["props"])})
            async for rec in await session.run(
                "MATCH (a)-[r]->(b) RETURN elementId(a) AS src, elementId(b) AS dst, "
                "type(r) AS type, properties(r) AS props"
            ):
                rels.append({"src": rec["src"], "dst": rec["dst"], "type": rec["type"], "props": _serialize(rec["props"])})

            async def rows(query: str) -> list[dict]:
                try:
                    return [dict(r) async for r in await session.run(query)]
                except Exception as exc:  # noqa: BLE001 — procedimento indisponível não bloqueia o dump
                    print(f"[aviso] {query.split()[0]} {query.split()[1] if len(query.split()) > 1 else ''} falhou: {exc}")
                    return []

            comps = await rows("CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition")
            schema["components"] = [_serialize(r) for r in comps]
            schema["constraints"] = [_serialize(r) for r in await rows("SHOW CONSTRAINTS YIELD * RETURN *")]
            schema["indexes"] = [_serialize(r) for r in await rows("SHOW INDEXES YIELD * RETURN *")]
            schema["labels"] = [r["label"] for r in await rows("CALL db.labels() YIELD label RETURN label")]
            schema["relationship_types"] = [
                r["type"] for r in await rows("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType AS type")
            ]
            schema["property_keys"] = [r["key"] for r in await rows("CALL db.propertyKeys() YIELD propertyKey AS key RETURN key")]

            counts["nodes_total"] = len(nodes)
            counts["rels_total"] = len(rels)
            counts["by_label_combination"] = {
                json.dumps(sorted(r["ls"]), sort_keys=True): r["c"]
                for r in await rows("MATCH (n) UNWIND [labels(n)] AS ls RETURN ls, count(*) AS c")
            }
            counts["by_relationship_type"] = {
                r["type"]: r["c"] for r in await rows("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c")
            }
    finally:
        await driver.close()

    graph = {
        "format": "nexus_neo4j_full_export_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_host": uri.split("//")[-1],
        "nodes": nodes,
        "relationships": rels,
    }
    graph_hash = _canonical_hash({"nodes": nodes, "relationships": rels})
    schema_hash = _canonical_hash(schema)

    graph_path = out_dir / "graph_export.json"
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    shutil.copy2(Path(__file__).resolve(), out_dir / "aura_final_backup.py")

    manifest = {
        "manifest": "neo4j_aura_final_backup",
        "generated_at": graph["generated_at"],
        "source_host": graph["source_host"],
        "nodes_total": counts["nodes_total"],
        "rels_total": counts["rels_total"],
        "counts": counts,
        "graph_sha256": graph_hash,
        "schema_sha256": schema_hash,
        "files": {
            "graph_export.json": _file_sha256(graph_path),
            "schema.json": _file_sha256(out_dir / "schema.json"),
            "aura_final_backup.py": _file_sha256(out_dir / "aura_final_backup.py"),
        },
        "restore_usage": "python aura_final_backup.py restore --json graph_export.json --uri <alvo> --password <senha>",
        "read_only_on_source": True,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, ensure_ascii=False, indent=2))
    print(f"[pacote] {out_dir}")
    return 0


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grouped(items: list[dict], keyfn) -> dict[tuple, list[dict]]:
    groups: dict[tuple, list[dict]] = {}
    for item in items:
        groups.setdefault(keyfn(item), []).append(item)
    return groups


async def _restore(args: argparse.Namespace) -> int:
    from neo4j import AsyncGraphDatabase

    graph = json.loads(Path(args.json).read_text(encoding="utf-8"))
    if graph.get("format") != "nexus_neo4j_full_export_v1":
        raise SystemExit("formato de export desconhecido")

    driver = AsyncGraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        async with driver.session() as session:
            await session.run("MATCH (n) DETACH DELETE n")  # alvo limpo (Neo4j local de verificação)
            if args.keep_eid:
                await session.run(f"CREATE INDEX tmp_eid_idx IF NOT EXISTS FOR (n:{TEMP_LABEL}) ON (n._eid)")
            total_nodes = 0
            for labels, group in _grouped(graph["nodes"], lambda n: tuple(n["labels"])).items():
                rows = [{"props": {**n["props"], "_eid": n["eid"]}} for n in group]
                all_labels = list(labels) + ([TEMP_LABEL] if args.keep_eid else [])
                set_clause = ("SET n:" + ":".join(all_labels) + " ") if all_labels else ""
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i : i + BATCH_SIZE]
                    q = f"UNWIND $rows AS row CREATE (n) {set_clause}SET n = row.props"
                    await session.run(q, rows=batch)
                    total_nodes += len(batch)
            print(f"[restore] nós criados: {total_nodes}")

            total_rels = 0
            for rtype, group in _grouped(graph["relationships"], lambda r: r["type"]).items():
                rows = [{"src": r["src"], "dst": r["dst"], "props": r["props"]} for r in group]
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i : i + BATCH_SIZE]
                    if args.keep_eid:
                        q = (
                            f"UNWIND $rows AS row MATCH (a:{TEMP_LABEL} {{_eid: row.src}}) "
                            f"MATCH (b:{TEMP_LABEL} {{_eid: row.dst}}) "
                            f"CREATE (a)-[r:`{rtype}`]->(b) SET r = row.props"
                        )
                    else:
                        raise SystemExit("modo sem --keep-eid ainda não suportado para rels (usar --keep-eid)")
                    await session.run(q, rows=batch)
                    total_rels += len(batch)
            print(f"[restore] rels criadas: {total_rels}")
    finally:
        await driver.close()
    print("[restore] concluído — executar verify para comparação byte-a-byte")
    return 0


def _export_label_counts(graph: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in graph["nodes"]:
        key = json.dumps(sorted(n["labels"]), sort_keys=True)
        counts[key] = counts.get(key, 0) + 1
    return counts


async def _verify(args: argparse.Namespace) -> int:
    """Compara o alvo restaurado (com _eid preservado) contra o JSON canônico."""
    from neo4j import AsyncGraphDatabase

    graph = json.loads(Path(args.json).read_text(encoding="utf-8"))
    exp_nodes = sorted(
        [{"eid": n["eid"], "labels": sorted(n["labels"]), "props": _serialize(n["props"])} for n in graph["nodes"]],
        key=lambda x: x["eid"],
    )
    exp_rels = sorted(
        [{"src": r["src"], "dst": r["dst"], "type": r["type"], "props": _serialize(r["props"])} for r in graph["relationships"]],
        key=lambda x: (x["src"], x["dst"], x["type"]),
    )

    driver = AsyncGraphDatabase.driver(args.uri, auth=(args.user, args.password))
    got_nodes, got_rels = [], []
    try:
        async with driver.session() as session:
            async for rec in await session.run(
                "MATCH (n) RETURN elementId(n) AS eid, labels(n) AS labels, properties(n) AS props"
            ):
                labels = sorted(lbl for lbl in rec["labels"] if lbl != TEMP_LABEL)
                props = {k: _serialize({k: v})[k] for k, v in (rec["props"] or {}).items() if k != "_eid"}
                props["_eid_export"] = rec["props"].get("_eid")
                got_nodes.append({"eid": props.pop("_eid_export"), "labels": labels, "props": props})
            async for rec in await session.run(
                "MATCH (a)-[r]->(b) RETURN a._eid AS src, b._eid AS dst, type(r) AS type, properties(r) AS props"
            ):
                got_rels.append({"src": rec["src"], "dst": rec["dst"], "type": rec["type"], "props": _serialize(rec["props"])})
    finally:
        await driver.close()

    got_nodes = sorted(got_nodes, key=lambda x: x["eid"])
    got_rels = sorted(got_rels, key=lambda x: (x["src"], x["dst"], x["type"]))
    ok_nodes = got_nodes == exp_nodes
    ok_rels = got_rels == exp_rels
    print(f"verify nodes: {'OK' if ok_nodes else 'DIVERGE'} ({len(got_nodes)}/{len(exp_nodes)})")
    print(f"verify rels:  {'OK' if ok_rels else 'DIVERGE'} ({len(got_rels)}/{len(exp_rels)})")
    if not ok_nodes:
        for e, g in zip(exp_nodes, got_nodes):
            if e != g:
                print("  primeiro mismatch node:", json.dumps({"esperado": e, "obtido": g}, ensure_ascii=False)[:800])
                break
    if not ok_rels:
        for e, g in zip(exp_rels, got_rels):
            if e != g:
                print("  primeiro mismatch rel:", json.dumps({"esperado": e, "obtido": g}, ensure_ascii=False)[:800])
                break
    return 0 if (ok_nodes and ok_rels) else 1


async def _cleanup(args: argparse.Namespace) -> int:
    """Remove _eid e o label temporário do alvo restaurado + dropa o índice."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        async with driver.session() as session:
            await session.run(f"MATCH (n:{TEMP_LABEL}) REMOVE n._eid REMOVE n:{TEMP_LABEL}")
            await session.run("DROP INDEX tmp_eid_idx IF EXISTS")
    finally:
        await driver.close()
    print("[cleanup] _eid/temp label removidos — alvo pronto para uso")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup/restore/verify final do Neo4j Aura")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_exp = sub.add_parser("export", help="exporta grafo+schema (read-only)")
    p_exp.add_argument("--out", required=True, help="diretório de saída do pacote")
    p_exp.set_defaults(func=lambda a: _export(a))

    p_res = sub.add_parser("restore", help="recria o grafo num Neo4j alvo")
    p_res.add_argument("--json", required=True)
    p_res.add_argument("--uri", required=True)
    p_res.add_argument("--user", default="neo4j")
    p_res.add_argument("--password", required=True)
    p_res.add_argument("--keep-eid", action="store_true", help="preserva _eid/__TMP_EID para verify")
    p_res.set_defaults(func=lambda a: _restore(a))

    p_ver = sub.add_parser("verify", help="compara alvo restaurado vs JSON (byte-a-byte)")
    p_ver.add_argument("--json", required=True)
    p_ver.add_argument("--uri", required=True)
    p_ver.add_argument("--user", default="neo4j")
    p_ver.add_argument("--password", required=True)
    p_ver.set_defaults(func=lambda a: _verify(a))

    p_cln = sub.add_parser("cleanup", help="remove _eid/temp label do alvo")
    p_cln.add_argument("--uri", required=True)
    p_cln.add_argument("--user", default="neo4j")
    p_cln.add_argument("--password", required=True)
    p_cln.set_defaults(func=lambda a: _cleanup(a))

    args = parser.parse_args()
    return asyncio.run(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
