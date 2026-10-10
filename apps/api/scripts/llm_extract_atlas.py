"""#056.3 — Extração LLM das fontes de carreira do atlas DEFENDEU (alavanca 1).

Para cada source dos clusters DEFENDEU dos 7 candidatos no manifest: baixa a
página, extrai triplas com o LLMCanonicalExtractor (provider NEXUS_LLM_* —
router HF gratuito) e grava payloads para ingestão pelo pipeline (/api/ingest).

O pipeline do Space já refina (span validator + canonicalizer + aliases),
rejeita ruído e contabiliza — este script apenas amplia a CAPTURA.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402
import yaml  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
MAX_TEXT_CHARS = 12_000
ATLAS_PREDICATES = ["DEFENDEU", "PERTENCE_A", "LOCALIZADO_EM", "VENCEU", "POSSUIR", "CONECTA_A"]


def _page_text(url: str) -> str:
    response = requests.get(url, headers=UA, timeout=30)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type:
        return response.text[:MAX_TEXT_CHARS]
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)[:MAX_TEXT_CHARS]
    except ImportError:
        text = re.sub(r"<[^>]+>", " ", response.text)
        return re.sub(r"\s+", " ", text)[:MAX_TEXT_CHARS]


def atlas_source_urls(manifest: Path) -> list[str]:
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    urls: list[str] = []
    seen: set[str] = set()
    for cluster in data.get("clusters") or []:
        cid = str(cluster.get("id") or "")
        if not any(k in cid for k in ("garrincha", "jairzinho", "zito", "carlosalbertotorres",
                                      "romario", "socrates", "rogerioceni")):
            continue
        if str(cluster.get("expected_predicate") or "") != "DEFENDEU":
            continue
        for source in cluster.get("sources") or []:
            url = source.get("url") or ""
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description="#056.3 — LLM extraction das fontes do atlas")
    parser.add_argument("--manifest", default="config/seed_clusters.yaml")
    parser.add_argument("--out", default="data/llm_atlas_payloads.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="0 = todas as URLs do atlas")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    from src.cognition.llm_extractor import LLMCanonicalExtractor

    extractor = LLMCanonicalExtractor(allowed_predicates=ATLAS_PREDICATES)
    urls = atlas_source_urls(Path(args.manifest))
    if args.limit:
        urls = urls[: args.limit]
    print(f"URLs do atlas: {len(urls)}")

    out = Path(args.out)
    done = 0
    with out.open("w", encoding="utf-8") as handle:
        for i, url in enumerate(urls):
            try:
                text = _page_text(url)
            except Exception as exc:
                print(f"  [{i + 1}/{len(urls)}] fetch falhou {url[:60]}: {type(exc).__name__}")
                continue
            triplets = extractor.extract_canonical_triplets(text)
            entities = [
                {"subject": t["subject"], "predicate": t["predicate"],
                 "object": t["object"], "confidence": float(t.get("confidence", 0.9))}
                for t in triplets
            ]
            if not entities:
                print(f"  [{i + 1}/{len(urls)}] {url[:60]} -> 0 triplas")
                continue
            payload = {
                "source_url": url,
                "timestamp": int(time.time()),
                "domain_score": 0.85,
                "title": f"LLM extraction — {url[:60]}",
                "extracted_entities": entities,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            done += 1
            print(f"  [{i + 1}/{len(urls)}] {url[:60]} -> {len(entities)} triplas")
            time.sleep(2)
    print(f"payloads LLM: {done} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
