"""Warm-up read-only do Space: /health + /api/metrics até estabilizar."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(".env"))
    load_dotenv(Path(".env.local"))
except Exception:
    pass

import httpx

space = (os.environ.get("NEXUS_SPACE_URL") or os.environ.get("HF_SPACE_URL") or "").rstrip("/")
hf = os.environ.get("HF_TOKEN", "")
nexus = os.environ.get("NEXUS_API_TOKEN", "")
headers = {}
if hf:
    headers["Authorization"] = f"Bearer {hf}"
if nexus:
    headers["X-Nexus-Token"] = nexus

print(f"space={space}", flush=True)

stable_body = None
for i in range(1, 16):
    try:
        with httpx.Client(timeout=60.0, headers=headers) as client:
            hr = client.get(f"{space}/health")
            mr = client.get(f"{space}/api/metrics")
            print(f"--- attempt {i} ---", flush=True)
            print(f"health {hr.status_code} {hr.text[:300]}", flush=True)
            if mr.status_code != 200:
                print(f"metrics non-200 {mr.status_code} {mr.text[:300]}", flush=True)
                time.sleep(8)
                continue

            m = mr.json()
            ver = m.get("verification") or {}
            acct = m.get("ingestion_accounting") or {}
            eq = m.get("extraction_quality") or {}
            g = m.get("graph") or {}
            print(f"verification={json.dumps(ver, ensure_ascii=False)}", flush=True)
            print(f"duplicate_cross_domain={acct.get('duplicate_cross_domain')}", flush=True)
            print(f"canonical_to_fact_gap={acct.get('canonical_to_fact_gap')}", flush=True)
            print(f"unaccounted_raw={acct.get('unaccounted_raw')}", flush=True)
            print(f"facts(graph)={g.get('facts')}", flush=True)
            print(f"last_ingest_at={acct.get('last_ingest_at')}", flush=True)

            cold = (
                g.get("facts") == 0
                or ver.get("facts_with_two_or_more_domains") is None
                or "error" in m
            )
            if cold:
                print("possible cold-start; waiting...", flush=True)
                time.sleep(10)
                continue

            Path("reports").mkdir(exist_ok=True)
            Path("reports/_warm_metrics_047.json").write_text(
                json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print("STABLE and saved warm metrics", flush=True)
            stable_body = m
            break
    except Exception as exc:
        print(f"attempt {i} error {type(exc).__name__}: {exc}", flush=True)
        time.sleep(10)

if stable_body is None:
    print("FAILED to stabilize", flush=True)
    raise SystemExit(1)
