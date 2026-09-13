"""Nexus-Alpha — Agente do enxame para simulação de cenários.

Implementação **original** (stdlib puro) inspirada no conceito de inteligência de
enxame para predição (multi-agentes que interagem e convergem). Nenhum código de
terceiros foi copiado — projetos como o MiroFish são AGPL-3.0 e não podem ser
incorporados sem contaminar a licença da Nexus-Alpha.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SwarmAgent:
    """Nó do grafo elevado a agente com uma posição (stance) dinâmica.

    ``stance`` ∈ [0, 1] representa a expectativa/opinião do agente sobre o tema
    simulado. ``influence`` pondera o quanto ele arrasta os vizinhos (derivado do
    grau no grafo). ``neighbors`` são os nomes dos agentes conectados.
    """

    name: str
    stance: float = 0.5
    influence: float = 1.0
    neighbors: list[str] = field(default_factory=list)
    memory: list[str] = field(default_factory=list)

    def clamp(self) -> None:
        self.stance = min(1.0, max(0.0, self.stance))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "stance": round(self.stance, 4),
            "influence": round(self.influence, 3),
            "neighbors": len(self.neighbors),
        }
