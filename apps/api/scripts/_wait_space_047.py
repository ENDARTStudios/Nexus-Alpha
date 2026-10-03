"""Aguarda Space HF conter o código #047 (entity_aliases + strip_boundary_noise)."""
from __future__ import annotations

import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(".env"))
except Exception:
    pass

import httpx

hf = os.environ.get("HF_TOKEN", "")
headers = {"Authorization": f"Bearer {hf}"}

for i in range(1, 31):
    r = httpx.get(
        "https://huggingface.co/api/spaces/ENDARTStudios/Nexus-Alpha",
        headers=headers,
        timeout=30,
    )
    d = r.json()
    sha = (d.get("sha") or "")[:7]
    runtime = d.get("runtime") or {}
    stage = runtime.get("stage")
    rsha = (runtime.get("sha") or "")[:7]
    last_mod = d.get("lastModified")

    ra = httpx.get(
        "https://huggingface.co/spaces/ENDARTStudios/Nexus-Alpha/resolve/main/src/cognition/entity_aliases.yaml",
        headers=headers,
        timeout=30,
    )
    re = httpx.get(
        "https://huggingface.co/spaces/ENDARTStudios/Nexus-Alpha/resolve/main/src/cognition/extractor.py",
        headers=headers,
        timeout=30,
    )
    has_alias = ra.status_code == 200
    has_boundary = re.status_code == 200 and "strip_boundary_noise" in re.text
    print(
        f"i={i} repo_sha={sha} runtime_sha={rsha} stage={stage} "
        f"alias={has_alias} boundary={has_boundary} lastMod={last_mod}",
        flush=True,
    )
    if has_alias and has_boundary:
        print("CODE_OK", flush=True)
        break
    time.sleep(10)
else:
    print("TIMEOUT waiting for code", flush=True)
