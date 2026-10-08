"""TASK-003: checagem de site/Space/API sem imprimir segredos."""
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local")

out = ROOT / ".autonomous" / "runtime"
out.mkdir(parents=True, exist_ok=True)

VARS = [
    "HF_TOKEN",
    "HF_SPACE_URL",
    "NEXUS_API_TOKEN",
    "NEO4J_URI",
    "NEO4J_PASSWORD",
    "QDRANT_HOST",
    "QDRANT_API_KEY",
    "VERCEL_TOKEN",
    "GITHUB_TOKEN",
]
print("== presenca de credenciais (sem valores) ==")
presence = {}
for v in VARS:
    val = os.environ.get(v, "")
    presence[v] = bool(val)
    print(f"{v}={'present' if val else 'missing'}")

space_url = (os.environ.get("NEXUS_SPACE_URL") or os.environ.get("HF_SPACE_URL") or "").rstrip("/")
headers = {}
if os.environ.get("HF_TOKEN"):
    headers["Authorization"] = f"Bearer {os.environ['HF_TOKEN']}"
if os.environ.get("NEXUS_API_TOKEN"):
    headers["X-Nexus-Token"] = os.environ["NEXUS_API_TOKEN"]

result = {"credential_presence": presence, "space_url_configured": bool(space_url)}

site = "https://nexus-alpha-kappa.vercel.app"
site_attempts = []
with httpx.Client(follow_redirects=True, timeout=30.0) as c:
    for attempt in range(3):
        try:
            r = c.get(f"{site}/health")
            site_attempts.append({"attempt": attempt + 1, "status": r.status_code})
            if r.status_code == 200:
                (out / "site_health.json").write_text(r.text, encoding="utf-8")
                break
        except Exception as exc:
            site_attempts.append({"attempt": attempt + 1, "error": type(exc).__name__})
        time.sleep(5)
    result["site_health_attempts"] = site_attempts
    result["site_health_ok"] = any(a.get("status") == 200 for a in site_attempts)

    if space_url:
        space_attempts = []
        for attempt in range(3):
            try:
                r = c.get(f"{space_url}/health", headers=headers)
                space_attempts.append({"attempt": attempt + 1, "status": r.status_code})
                if r.status_code == 200:
                    (out / "space_health.json").write_text(r.text, encoding="utf-8")
                    break
            except Exception as exc:
                space_attempts.append({"attempt": attempt + 1, "error": type(exc).__name__})
            time.sleep(10)
        result["space_health_attempts"] = space_attempts
        result["space_health_ok"] = any(a.get("status") == 200 for a in space_attempts)

        try:
            r = c.get(f"{space_url}/api/metrics", headers=headers)
            result["metrics_status"] = r.status_code
            if r.status_code == 200:
                data = r.json()
                (out / "metrics.json").write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        except Exception as exc:
            result["metrics_error"] = type(exc).__name__

(out / "runtime_status.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(result, ensure_ascii=False, indent=2))

mpath = out / "metrics.json"
if mpath.exists():
    m = json.loads(mpath.read_text(encoding="utf-8"))
    print("== metrics keys ==", sorted(m.keys()))
    for k in ("cognitive_health", "graph", "extraction_quality", "ingestion_accounting",
              "verification", "fallback_health", "vectors"):
        if k in m:
            v = m[k]
            if k == "extraction_quality" and isinstance(v, dict):
                v = {kk: vv for kk, vv in v.items() if kk != "rejection_reasons"}
            print(f"  {k} = {json.dumps(v, ensure_ascii=False)[:500]}")
    eq = m.get("extraction_quality") or {}
    print("  rejection_reasons =", json.dumps(eq.get("rejection_reasons", {}), ensure_ascii=False)[:400])
