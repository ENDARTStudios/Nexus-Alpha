"""Conversão de fatos verificados da Nexus-Alpha para formato Alpaca/LlamaFactory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DATASET_NAME = "nexus_verified_facts"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _extract_domains(value: Any) -> list[str]:
    if not value:
        return []

    if isinstance(value, str):
        return [_clean(value)] if _clean(value) else []

    domains: list[str] = []
    if isinstance(value, Iterable) and not isinstance(value, (dict, bytes)):
        for item in value:
            if isinstance(item, str):
                domain = _clean(item)
            elif isinstance(item, dict):
                domain = _clean(item.get("domain") or item.get("url") or item.get("source"))
            else:
                domain = ""
            if domain:
                domains.append(domain)

    # Preserva ordem e remove duplicatas.
    seen: set[str] = set()
    unique: list[str] = []
    for domain in domains:
        if domain not in seen:
            seen.add(domain)
            unique.append(domain)
    return unique


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _canonical_fact_hash(subject: str, predicate: str, obj: str) -> str:
    raw = f"{subject.lower().strip()}|{predicate.lower().strip()}|{obj.lower().strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_fact(fact: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(fact, dict):
        return None

    # Se houver flag explícita de não verificado, ignora.
    verified = fact.get("verified", fact.get("verificado", True))
    if verified is False:
        return None

    subject = _clean(fact.get("subject") or fact.get("sujeito"))
    predicate = _clean(fact.get("predicate") or fact.get("predicado"))
    obj = _clean(fact.get("object") or fact.get("objeto"))

    if not subject or not predicate or not obj:
        return None

    domains = _extract_domains(
        fact.get("source_domains") or fact.get("domains") or fact.get("sources")
    )
    confirmations = _to_int(
        fact.get("confirmations") or fact.get("confirmacoes"), 0
    )

    if confirmations <= 0:
        confirmations = len(domains)

    # Fato verificado deve ter ao menos uma corroboração utilizável.
    if confirmations <= 0:
        confirmations = 1

    fact_hash = _clean(fact.get("fact_hash")) or _canonical_fact_hash(
        subject, predicate, obj
    )

    return {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "fact_hash": fact_hash,
        "confirmations": confirmations,
        "source_domains": domains,
    }


def fact_to_alpaca(fact: dict[str, Any]) -> dict[str, str] | None:
    """Converte um fato verificado em registro Alpaca: instruction/input/output."""
    normalized = _normalize_fact(fact)
    if normalized is None:
        return None

    subject = normalized["subject"]
    predicate = normalized["predicate"]
    obj = normalized["object"]
    confirmations = normalized["confirmations"]
    domains = normalized["source_domains"]

    domains_text = ", ".join(domains) if domains else "não informado"
    corroboration = (
        "uma fonte independente" if confirmations == 1 else f"{confirmations} fontes independentes"
    )

    instruction = (
        f"Explique, com base apenas em fatos verificados, a relação entre {subject} e {obj}."
    )
    model_input = (
        f"Predicado: {predicate}\n"
        f"Corroborações: {confirmations}\n"
        f"Domínios de origem: {domains_text}"
    )
    output = (
        f"{subject} {predicate} {obj}. Essa relação foi corroborada por {corroboration}."
    )

    return {
        "instruction": instruction,
        "input": model_input,
        "output": output,
    }


def build_dataset(
    facts: Iterable[dict[str, Any]],
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    jsonl_filename: str | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Constrói registros Alpaca e o bloco correspondente de dataset_info.json."""
    jsonl_filename = jsonl_filename or f"{dataset_name}.jsonl"

    records: list[dict[str, str]] = []
    for fact in facts:
        record = fact_to_alpaca(fact)
        if record is not None:
            records.append(record)

    dataset_info = {
        dataset_name: {
            "file_name": jsonl_filename,
            "columns": {
                "prompt": "instruction",
                "query": "input",
                "response": "output",
            },
        }
    }

    return records, dataset_info


def write_dataset(
    out_dir: str | Path,
    facts: Iterable[dict[str, Any]],
    *,
    dataset_name: str = DEFAULT_DATASET_NAME,
    jsonl_filename: str | None = None,
) -> dict[str, Any]:
    """Grava JSONL e atualiza/cria dataset_info.json no diretório de saída."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    jsonl_filename = jsonl_filename or f"{dataset_name}.jsonl"
    records, info_block = build_dataset(
        facts,
        dataset_name=dataset_name,
        jsonl_filename=jsonl_filename,
    )

    jsonl_path = out_path / jsonl_filename
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    info_path = out_path / "dataset_info.json"
    existing: dict[str, Any] = {}
    if info_path.exists():
        try:
            loaded = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = {}

    existing.update(info_block)
    info_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    return {
        "dataset_dir": str(out_path),
        "jsonl_path": str(jsonl_path),
        "dataset_info_path": str(info_path),
        "dataset_name": dataset_name,
        "records": len(records),
    }
