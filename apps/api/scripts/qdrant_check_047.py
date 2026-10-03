"""Verifica Qdrant (read-only): contagem de pontos após reset de Fatos."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
except Exception:
    pass


def main() -> None:
    from qdrant_client import QdrantClient

    host = os.environ.get("QDRANT_HOST", "")
    key = os.environ.get("QDRANT_API_KEY", "")
    if not host:
        print("QDRANT_HOST ausente — abortando verificação")
        raise SystemExit(1)

    if host.startswith(("http://", "https://")):
        client = QdrantClient(url=host, api_key=key or None, timeout=30)
    else:
        client = QdrantClient(url=f"https://{host}", api_key=key or None, timeout=30)
    collections = client.get_collections().collections
    out = {
        "report": "qdrant_check_047",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host.split("//")[-1].split("?")[0],
        "collections": [],
        "truthfulness_note": "Read-only Qdrant check; no deletes.",
    }
    for c in collections:
        info = client.count(c.name, exact=True)
        out["collections"].append({"name": c.name, "points": info.count})
        print(f"{c.name}: {info.count} points")

    path = Path("reports/qdrant_check_047.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[salvo em] {path}")


if __name__ == "__main__":
    main()
