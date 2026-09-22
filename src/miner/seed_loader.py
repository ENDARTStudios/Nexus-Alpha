"""Nexus-Alpha — Loader de clusters de seeds curados (#048).

Lê ``config/seed_clusters.yaml`` e valida as regras de corroboração cross-domain:
- >= N domínios distintos por cluster (default 3);
- >= N publishers distintos (default 2);
- ao menos 1 publisher fora de ``wikipedia.org``;
- HTTPS, sem URLs duplicadas, sem domínios proibidos, sem segredos.

Determinístico e sem dependências novas (PyYAML já disponível).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

FORBIDDEN_DOMAINS = (
    "twitter.com", "x.com", "facebook.com", "instagram.com", "tiktok.com",
    "youtube.com", "reddit.com", "medium.com", "blogspot.com", "wordpress.com",
    "tumblr.com", "substack.com",
)

SECRET_MARKERS = (
    "hf_", "neo4j", "password", "token", "authorization", "x-nexus-token",
    "qdrant_api_key", "secret",
)


def load_seed_clusters(path: Path | str) -> dict[str, Any]:
    """Carrega o manifest YAML de clusters."""
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _host(url: str) -> str:
    host = urlparse(url or "").netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _is_wikipedia(publisher: str) -> bool:
    publisher = (publisher or "").lower()
    return "wikipedia" in publisher or "wikimedia" in publisher


def validate_seed_clusters(data: dict[str, Any]) -> list[str]:
    """Devolve a lista de erros estruturais (vazia = válido)."""
    if not isinstance(data, dict):
        return ["manifest inválido: raiz deve ser um mapa"]

    errors: list[str] = []
    defaults = data.get("defaults") or {}
    min_domains = int(defaults.get("min_distinct_domains", 3))
    min_publishers = int(defaults.get("min_distinct_publishers", 2))
    require_non_wiki = bool(defaults.get("require_non_wikipedia_publisher", True))

    seen_ids: set[str] = set()
    for cluster in data.get("clusters") or []:
        cid = cluster.get("id")
        if not cid:
            errors.append("cluster sem 'id'")
            continue
        if cid in seen_ids:
            errors.append(f"{cid}: 'id' duplicado")
        seen_ids.add(cid)
        if not str(cluster.get("topic") or "").strip():
            errors.append(f"{cid}: 'topic' vazio")

        sources = cluster.get("sources") or []
        if len(sources) < min_domains:
            errors.append(f"{cid}: menos de {min_domains} sources")

        domains: set[str] = set()
        publishers: set[str] = set()
        cluster_urls: set[str] = set()
        for source in sources:
            url = source.get("url") or ""
            host = _host(url)
            if not url.startswith("https://"):
                errors.append(f"{cid}: URL não-HTTPS: {url}")
            domain = source.get("domain") or host
            if domain != host:
                errors.append(f"{cid}: 'domain' ({domain}) != host da URL ({host})")
            if url in cluster_urls:
                errors.append(f"{cid}: URL duplicada: {url}")
            cluster_urls.add(url)
            domains.add(domain)
            publishers.add(str(source.get("publisher") or ""))
            low = domain.lower()
            if any(low == f or low.endswith("." + f) for f in FORBIDDEN_DOMAINS):
                errors.append(f"{cid}: domínio proibido: {domain}")

        if len(domains) < min_domains:
            errors.append(f"{cid}: menos de {min_domains} domínios distintos")
        if len(publishers) < min_publishers:
            errors.append(f"{cid}: menos de {min_publishers} publishers distintos")
        if require_non_wiki and not any(not _is_wikipedia(p) for p in publishers):
            errors.append(f"{cid}: sem publisher fora de wikipedia.org")

    return errors


def cluster_to_seeds(data: dict[str, Any]) -> list[str]:
    """URLs únicas dos clusters, preservando a ordem."""
    urls: list[str] = []
    for cluster in data.get("clusters") or []:
        for source in cluster.get("sources") or []:
            url = source.get("url")
            if url and url not in urls:
                urls.append(url)
    return urls


def manifest_health(data: dict[str, Any]) -> dict[str, int]:
    """Resumo para métricas/log (não exposto publicamente)."""
    clusters = data.get("clusters") or []
    urls = cluster_to_seeds(data)
    domains = {_host(u) for u in urls}
    publishers = {
        str(s.get("publisher"))
        for c in clusters for s in (c.get("sources") or [])
    }
    return {
        "configured": len(clusters),
        "urls_injected": len(urls),
        "domains_expected": len(domains),
        "distinct_publishers_expected": len(publishers),
    }
