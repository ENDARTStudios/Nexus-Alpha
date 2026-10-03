"""Auditoria de CORS do Space (preflight OPTIONS).

Utilitário de linha de comando — NÃO é coletado pelo pytest (não casa `test_*.py`).

Uso:
    python tests/check_cors.py

Variáveis opcionais:
    NEXUS_SPACE_URL    (default: https://endartstudios-nexus-alpha.hf.space)
    NEXUS_SITE_ORIGIN  (default: https://nexus-alpha.vercel.app)
    HF_TOKEN           (necessário para Spaces privados)
"""
from __future__ import annotations

import os

import httpx

DEFAULT_SPACE = "https://endartstudios-nexus-alpha.hf.space"
TARGET_URL = os.environ.get("NEXUS_SPACE_URL", DEFAULT_SPACE).rstrip("/") + "/api/chat"
ORIGIN_SITE = os.environ.get("NEXUS_SITE_ORIGIN", "https://nexus-alpha.vercel.app")


def _token() -> str | None:
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    try:
        from huggingface_hub import get_token

        return get_token()
    except Exception:
        return None


def audit_cors_headers() -> bool:
    headers = {
        "Origin": ORIGIN_SITE,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    token = _token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"Preflight OPTIONS contra: {TARGET_URL}")
    print(f"Origin simulada: {ORIGIN_SITE}")
    try:
        response = httpx.options(TARGET_URL, headers=headers, timeout=20.0)
    except Exception as exc:
        print(f"Falha crítica de comunicação na auditoria de rede: {exc}")
        return False

    allow_origin = response.headers.get("access-control-allow-origin")
    allow_methods = response.headers.get("access-control-allow-methods")
    allow_headers = response.headers.get("access-control-allow-headers")

    print(f"Status HTTP: {response.status_code}")
    print("--- Relatório de Auditoria de Cabeçalhos ---")
    print(f"Access-Control-Allow-Origin: {allow_origin}")
    print(f"Access-Control-Allow-Methods: {allow_methods}")
    print(f"Access-Control-Allow-Headers: {allow_headers}")

    if allow_origin in ("*", ORIGIN_SITE):
        print("CÓRTEX SEGURO: CORS validado. O site conseguirá conversar com o chatbot.")
        return True
    print("ALERTA: cabeçalho Access-Control-Allow-Origin ausente ou restritivo.")
    return False


if __name__ == "__main__":
    raise SystemExit(0 if audit_cors_headers() else 1)
