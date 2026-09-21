"""Nexus-Alpha — Sistema de memória inspirado no cérebro humano.

Três camadas, espelhando a dinâmica córtex/hipocampo:

* **Working Memory** (córtex pré-frontal): slots de ativação com decaimento —
  mantém conceitos "acesos" temporariamente durante o raciocínio.
* **Episodic Memory** (hipocampo): log temporal append-only dos eventos vividos.
* **Semantic Memory** (córtex temporal): fatos consolidados no grafo. O ciclo de
  consolidação (rede de modo padrão / "sono") reprocessa os episódios e promove
  o que se repete, fortalecendo arestas por **Hebbian learning**.

Inclui **associação inversa automática** (se A -> B, registra B -> A) e
**aprendizado contínuo**: fatos novos entram como subgrafo isolado e só ganham
pontes para o grafo antigo após repetição — evitando esquecimento catastrófico.

Tudo em stdlib; a persistência semântica é delegada ao ``GraphConnector``.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .regions import region_for


logger = logging.getLogger(__name__)


def resolve_writable_dir(preferred: Path, fallback_name: str = "nexus_brain") -> Path:
    """Devolve o primeiro diretório gravável entre o preferido e o temp do sistema.

    Necessário porque o Space pode ter um volume/bucket somente-leitura montado em
    ``data/``; nesse caso caímos para ``$TMPDIR`` sem quebrar o pipeline.
    """
    candidates = [preferred, Path(tempfile.gettempdir()) / fallback_name]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return candidate
        except Exception:
            continue
    return Path(tempfile.gettempdir())


INVERSE_PREDICATES: dict[str, str] = {
    "UTILIZA": "UTILIZADO_POR",
    "UTILIZADO_POR": "UTILIZA",
    "PERTENCE_A": "CONTIENE",
    "CONTIENE": "PERTENCE_A",
    "PRODUZ": "PRODUZIDO_POR",
    "PRODUZIDO_POR": "PRODUZ",
    "EXECUTA": "EXECUTADO_POR",
    "EXECUTADO_POR": "EXECUTA",
    "CONECTA_A": "CONECTA_A",
    "DERIVA_DE": "ORIGINA",
    "ORIGINA": "DERIVA_DE",
}


@dataclass
class Episode:
    timestamp: float
    kind: str
    content: dict[str, Any] = field(default_factory=dict)


class WorkingMemory:
    """Slots de ativação com expiração (capacidade limitada, como o córtex)."""

    def __init__(self, capacity: int = 7, decay_seconds: float = 300.0) -> None:
        self.capacity = capacity
        self.decay_seconds = decay_seconds
        self._slots: dict[str, float] = {}

    def activate(self, concept: str, now: Optional[float] = None) -> None:
        concept = (concept or "").strip()
        if not concept:
            return
        now = now if now is not None else time.time()
        self._slots[concept] = now + self.decay_seconds
        self._enforce_capacity()

    def _enforce_capacity(self) -> None:
        if len(self._slots) <= self.capacity:
            return
        for concept, _ in sorted(self._slots.items(), key=lambda kv: kv[1])[
            : len(self._slots) - self.capacity
        ]:
            del self._slots[concept]

    def active(self, now: Optional[float] = None) -> list[str]:
        now = now if now is not None else time.time()
        return [c for c, expiry in self._slots.items() if expiry > now]

    def decay(self, now: Optional[float] = None) -> int:
        """Remove slots expirados. Retorna quantos foram removidos."""
        now = now if now is not None else time.time()
        expired = [c for c, expiry in self._slots.items() if expiry <= now]
        for concept in expired:
            del self._slots[concept]
        return len(expired)

    def focus(self, now: Optional[float] = None) -> Optional[str]:
        active = self.active(now)
        return active[-1] if active else None

    def clear(self) -> None:
        self._slots.clear()


class EpisodicMemory:
    """Log temporal append-only (hipocampo virtual)."""

    def __init__(
        self,
        path: Optional[Path | str] = None,
        max_entries: int = 5000,
    ) -> None:
        if path is None:
            base = Path(os.environ.get("NEXUS_BRAIN_DIR", "data/brain"))
            base = resolve_writable_dir(base)
            path = base / "episodes.jsonl"
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries

    def record(self, kind: str, content: Optional[dict[str, Any]] = None) -> Episode:
        episode = Episode(timestamp=time.time(), kind=kind, content=content or {})
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(episode), ensure_ascii=False) + "\n")
        return episode

    def replay(self, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]

    def count(self) -> int:
        if not self.path.exists():
            return 0
        with self.path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())

    def prune(self) -> int:
        """Mantém apenas as ``max_entries`` mais recentes. Retorna quantos removeu."""
        if not self.path.exists():
            return 0
        lines = [line for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(lines) <= self.max_entries:
            return 0
        removed = len(lines) - self.max_entries
        self.path.write_text("\n".join(lines[-self.max_entries:]) + "\n", encoding="utf-8")
        return removed


class BrainMemorySystem:
    """Orquestra working + episódica + consolidação semântica (Hebbian)."""

    def __init__(
        self,
        working: Optional[WorkingMemory] = None,
        episodic: Optional[EpisodicMemory] = None,
        min_replays: int = 3,
        graph: Any = None,
        bidirectional: bool = True,
    ) -> None:
        self.working = working or WorkingMemory()
        self.episodic = episodic or EpisodicMemory()
        self.min_replays = min_replays
        self.graph = graph
        self.bidirectional = bidirectional
        self.coactivations: dict[tuple[str, str], int] = {}

    # ---- working memory -------------------------------------------------
    def attend(self, concepts: Iterable[str]) -> list[str]:
        for concept in concepts:
            self.working.activate(concept)
        self._learn_coactivations(self.working.active())
        return self.working.active()

    def _learn_coactivations(self, active: list[str]) -> None:
        """Hebbian: conceitos ativos juntos reforçam a associação entre si."""
        for i, a in enumerate(active):
            for b in active[i + 1 :]:
                key = tuple(sorted((a, b)))
                self.coactivations[key] = self.coactivations.get(key, 0) + 1

    # ---- episodic memory ------------------------------------------------
    def record_episode(self, kind: str, content: Optional[dict[str, Any]] = None) -> Episode:
        return self.episodic.record(kind, content)

    # ---- consolidação ("sono") -----------------------------------------
    def tally_replays(self, limit: int = 500) -> dict[tuple[str, str, str], int]:
        """Conta triplas (subject, predicate, object) repetidas nos episódios."""
        tally: dict[tuple[str, str, str], int] = {}
        for episode in self.episodic.replay(limit=limit):
            content = episode.get("content") or {}
            entities = content.get("extracted_entities") or []
            for item in entities:
                subject = str(item.get("subject", "")).strip().upper()
                predicate = str(item.get("predicate", "")).strip().upper()
                obj = str(item.get("object", "")).strip().upper()
                if subject and predicate and obj:
                    key = (subject, predicate, obj)
                    tally[key] = tally.get(key, 0) + 1
        return tally

    def consolidation_candidates(self, limit: int = 500) -> list[dict[str, Any]]:
        """Fatos que atingiram o limiar de repetição (prontos para o grafo semântico)."""
        candidates = []
        for (subject, predicate, obj), replays in self.tally_replays(limit).items():
            if replays >= self.min_replays:
                candidates.append({
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "replays": replays,
                })
        candidates.sort(key=lambda item: item["replays"], reverse=True)
        return candidates

    @staticmethod
    def inverse_of(predicate: str) -> Optional[str]:
        return INVERSE_PREDICATES.get((predicate or "").strip().upper())

    async def consolidate(self, limit: int = 500) -> dict[str, Any]:
        """Ciclo de 'sono': promove fatos repetidos ao grafo (+ arestas inversas)."""
        candidates = self.consolidation_candidates(limit=limit)
        inverses = []
        if self.bidirectional:
            for fact in candidates:
                inverse = self.inverse_of(fact["predicate"])
                if inverse:
                    inverses.append({
                        "subject": fact["object"],
                        "predicate": inverse,
                        "object": fact["subject"],
                        "replays": fact["replays"],
                    })

        total = 0
        if self.graph is not None and (candidates or inverses):
            try:
                total = await self.graph.consolidate_facts(candidates + inverses)
            except Exception as exc:
                logger.warning("Consolidação semântica indisponível: %s", exc)

        self.working.decay()
        self.episodic.prune()
        report = {
            "status": "ok",
            "candidates": len(candidates),
            "inverses": len(inverses),
            "consolidated": total,
            "min_replays": self.min_replays,
            "bidirectional": self.bidirectional,
            "episodes": self.episodic.count(),
        }
        logger.info("Consolidação (sono): %s", report)
        return report

    def stats(self) -> dict[str, Any]:
        return {
            "working_active": self.working.active(),
            "working_capacity": self.working.capacity,
            "working_region": region_for("working").name,
            "episodes": self.episodic.count(),
            "episodic_region": region_for("episodic").name,
            "semantic_region": region_for("semantic").name,
            "min_replays": self.min_replays,
            "hebbian_pairs": len(self.coactivations),
        }
