"""Nexus-Alpha — Quarentena persistente para fatos com baixa confiança.

Grava payloads rejeitados pelo SecurityProtocol em JSONL sob
`data/quarentena/quarentena.jsonl`. Cada entrada carrega motivo do
rejeição, timestamp e o NexusPayload original para reprocessamento.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

DEFAULT_DIR = Path("data/quarentena")


class QuarantineStore:
    def __init__(self, base_dir: Path | str = DEFAULT_DIR) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.base_dir / "quarentena.jsonl"

    def put(self, payload: dict[str, Any], reason: str, score: float) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "score": score,
            "payload": payload,
        }
        with self.file_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info("Fato em quarentena (%s, score=%.2f): %s", reason, score, payload.get("source_url"))

    def list_all(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []
        return [json.loads(line) for line in self.file_path.read_text(encoding="utf-8").splitlines() if line]

    def clear(self) -> None:
        if self.file_path.exists():
            self.file_path.unlink()

    def reprocess_candidates(self, min_score: float = 0.5) -> Iterable[dict[str, Any]]:
        for record in self.list_all():
            if record.get("score", 0.0) >= min_score:
                yield record

    def _rewrite(self, records: list[dict[str, Any]]) -> None:
        if not records:
            self.clear()
            return
        with self.file_path.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def remove_at(self, index: int) -> dict[str, Any] | None:
        """Remove e retorna o registro no índice (ordem de list_all)."""
        records = self.list_all()
        if 0 <= index < len(records):
            removed = records.pop(index)
            self._rewrite(records)
            logger.info("Registro de quarentena removido (índice %d).", index)
            return removed
        return None

    def approve_at(self, index: int) -> dict[str, Any] | None:
        """Aprovação forçada: remove da quarentena e retorna o payload para ingestão."""
        record = self.remove_at(index)
        if record is not None:
            logger.info(
                "Fato aprovado forçadamente por operador humano: %s",
                record.get("payload", {}).get("source_url", record.get("payload")),
            )
        return record

    def discard_at(self, index: int) -> dict[str, Any] | None:
        """Descarte definitivo: remove da quarentena sem promover ao grafo."""
        record = self.remove_at(index)
        if record is not None:
            logger.info("Fato descartado definitivamente por operador humano (índice %d).", index)
        return record