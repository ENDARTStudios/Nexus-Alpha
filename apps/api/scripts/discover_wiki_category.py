"""#056.2 — Descoberta de seeds em escala via categorias da Wikipedia (pt).

Quebra a limitação do acervo curado: membros de categorias (ex.
"Categoria:Futebolistas do Clube de Regatas do Flamengo") viram URLs de artigos
prontas para os clusters de seed — o worker mineria e corrobora os fatos
estruturados (Wikidata) como 3º domínio.

Uso: python scripts/discover_wiki_category.py --category "Categoria:Futebolistas do Santos FC" --limit 60
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://pt.wikipedia.org/w/api.php"
USER_AGENT = "Nexus-Alpha/1.0 category discovery (contato: endart.studios@gmail.com)"


def category_members(category: str, limit: int = 500) -> list[str]:
    titles: list[str] = []
    continue_from: str = ""
    while len(titles) < limit:
        params = {
            "action": "query", "list": "categorymembers", "cmtitle": category,
            "cmlimit": "500", "format": "json",
        }
        if continue_from:
            params["cmcontinue"] = continue_from
        url = API + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        members = data.get("query", {}).get("categorymembers", [])
        for member in members:
            if member["ns"] == 0 and (member.get("title") or "").strip():  # artigos
                titles.append(member["title"])
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
        continue_from = cont
    return titles[:limit]


def article_urls(titles: list[str]) -> list[str]:
    """Converte títulos em URLs canônicas (uma chamada batch)."""
    urls: list[str] = []
    for i in range(0, len(titles), 50):
        chunk = titles[i : i + 50]
        params = {
            "action": "query", "titles": "|".join(chunk), "format": "json",
            "redirects": 1,
        }
        url = API + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        for page in data.get("query", {}).get("pages", {}).values():
            title = (page.get("title") or "").replace(" ", "_")
            if int(page.get("pageid", 0)) > 0 and title:
                urls.append("https://pt.wikipedia.org/wiki/" + urllib.parse.quote(title))
    return urls


def main() -> int:
    parser = argparse.ArgumentParser(description="#056.2 — discovery de seeds por categoria")
    parser.add_argument("--category", required=True)
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    titles = category_members(args.category, args.limit)
    urls = article_urls(titles)
    print(json.dumps({"category": args.category, "membros": len(titles), "urls": len(urls)}, ensure_ascii=False))
    if args.out:
        Path(args.out).write_text("\n".join(urls), encoding="utf-8")
        print(f"[salvo] {args.out}")
    else:
        for url in urls[:15]:
            print(" ", url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
