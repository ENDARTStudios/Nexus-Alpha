"""Conftest da raiz — permite `pytest apps/api` a partir da raiz do monorepo.

Os gates oficiais (CI) rodam com working-directory apps/api; este conftest é
apenas conveniência local, inserindo apps/api no sys.path para que os imports
de `app`, `src.*` e `scripts.*` resolvam em qualquer CWD.
"""
from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
