"""Nexus-Alpha — Motor de simulação de enxame (predição sobre o grafo).

Constrói um "mundo digital" leve a partir do grafo de conhecimento: cada
conceito vira um agente com uma posição (``stance``), arestas viram canais de
influência, e a simulação roda rodadas de dinâmica de opinião com *bounded
confidence* até convergir (ou polarizar). O relatório final indica o cenário
predominante — convergência, polarização ou divergência — com nível de confiança.

Conceito inspirado em motores de predição por enxame (ex.: MiroFish), mas
implementado de forma original e sem dependências, respeitando o Custo Zero e a
licença AGPL de terceiros (não reutilizada).
"""
from __future__ import annotations

import logging
import random
from typing import Any, Iterable, Optional

from .agent import SwarmAgent


logger = logging.getLogger(__name__)


class SwarmSimulator:
    def __init__(
        self,
        agents: dict[str, SwarmAgent],
        alpha: float = 0.35,
        confidence_threshold: float = 0.25,
        edge_count: int = 0,
    ) -> None:
        self.agents = agents
        self.alpha = alpha
        self.confidence_threshold = confidence_threshold
        self.edge_count = edge_count

    # ---- construção a partir do grafo -------------------------------------
    @classmethod
    def from_topology(
        cls,
        topology: dict[str, Any],
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> "SwarmSimulator":
        nodes = topology.get("nodes", []) or []
        links = topology.get("links", []) or []

        adjacency: dict[str, set[str]] = {node["id"]: set() for node in nodes}
        edge_count = 0
        for link in links:
            source = link.get("source")
            target = link.get("target")
            if source in adjacency and target in adjacency and source != target:
                if target not in adjacency[source]:
                    edge_count += 1
                adjacency[source].add(target)
                adjacency[target].add(source)

        rng = random.Random(seed) if seed is not None else None
        agents: dict[str, SwarmAgent] = {}
        for node in nodes:
            name = node["id"]
            stance = 0.5 if rng is None else round(rng.uniform(0.2, 0.8), 4)
            agents[name] = SwarmAgent(
                name=name,
                stance=stance,
                influence=float(max(1, len(adjacency[name]))),
                neighbors=sorted(adjacency[name]),
            )
        return cls(agents, edge_count=edge_count, **kwargs)

    @classmethod
    def from_relations(
        cls,
        rows: Iterable[dict[str, Any]],
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> "SwarmSimulator":
        """Seeda a partir de linhas {subject, predicate, object} (ex.: search_context)."""
        nodes: dict[str, dict] = {}
        links: list[dict] = []
        for row in rows:
            subject = row.get("subject")
            obj = row.get("object")
            if not subject or not obj:
                continue
            nodes.setdefault(subject, {"id": subject})
            nodes.setdefault(obj, {"id": obj})
            links.append({"source": subject, "target": obj})
        return cls.from_topology(
            {"nodes": list(nodes.values()), "links": links}, seed=seed, **kwargs
        )

    # ---- manipulação e execução -------------------------------------------
    def inject(self, injections: Optional[dict[str, float]]) -> int:
        """Visão divina: fixa a posição de agentes específicos. Retorna quantos aplicou."""
        if not injections:
            return 0
        applied = 0
        for name, value in injections.items():
            agent = self.agents.get(name)
            if agent is not None:
                agent.stance = min(1.0, max(0.0, float(value)))
                applied += 1
        return applied

    def snapshot(self) -> dict[str, float]:
        return {name: round(agent.stance, 4) for name, agent in self.agents.items()}

    def run(self, rounds: int = 12) -> list[dict[str, float]]:
        rounds = max(0, min(int(rounds), 50))
        history: list[dict[str, float]] = [self.snapshot()]

        for _ in range(rounds):
            updated: dict[str, float] = {}
            for name, agent in self.agents.items():
                neighbor_agents = [
                    self.agents[n] for n in agent.neighbors if n in self.agents
                ]
                if not neighbor_agents:
                    updated[name] = agent.stance
                    continue

                close = [
                    n for n in neighbor_agents
                    if abs(n.stance - agent.stance) <= self.confidence_threshold
                ]
                pool = close or neighbor_agents
                total_weight = sum(n.influence for n in pool)
                target = (
                    sum(n.stance * n.influence for n in pool) / total_weight
                    if total_weight
                    else agent.stance
                )
                updated[name] = min(
                    1.0, max(0.0, (1 - self.alpha) * agent.stance + self.alpha * target)
                )

            for name, value in updated.items():
                self.agents[name].stance = value
            history.append(self.snapshot())

        return history

    # ---- relatório ---------------------------------------------------------
    def report(self, history: Optional[list[dict[str, float]]] = None) -> dict[str, Any]:
        history = history or [self.snapshot()]
        stances = [agent.stance for agent in self.agents.values()]
        count = len(stances)

        if count == 0:
            return {
                "status": "empty",
                "summary": "Grafo sem conceitos para simular.",
                "agent_count": 0,
                "edge_count": 0,
                "rounds": 0,
                "trajectory": [],
            }

        mean = sum(stances) / count
        variance = sum((s - mean) ** 2 for s in stances) / count
        std = variance ** 0.5
        consensus = max(0.0, min(1.0, 1.0 - 2.0 * std))
        polarization = sum(1 for s in stances if s <= 0.3 or s >= 0.7) / count

        density = self.edge_count / max(1, count * (count - 1) / 2)
        confidence = round(0.6 * consensus + 0.4 * min(1.0, density), 3)

        dominant = max(self.agents.values(), key=lambda a: a.stance)
        weakest = min(self.agents.values(), key=lambda a: a.stance)

        clusters: dict[str, int] = {}
        for stance in stances:
            bucket = str(round(stance, 1))
            clusters[bucket] = clusters.get(bucket, 0) + 1

        if consensus >= 0.75:
            verdict = "convergencia"
        elif polarization >= 0.5:
            verdict = "polarizacao"
        else:
            verdict = "divergencia_moderada"

        return {
            "status": "ok",
            "verdict": verdict,
            "consensus": round(consensus, 3),
            "polarization": round(polarization, 3),
            "mean_stance": round(mean, 3),
            "std_stance": round(std, 3),
            "confidence": confidence,
            "dominant": {"concept": dominant.name, "stance": round(dominant.stance, 3)},
            "weakest": {"concept": weakest.name, "stance": round(weakest.stance, 3)},
            "clusters": dict(sorted(clusters.items())),
            "agent_count": count,
            "edge_count": self.edge_count,
            "rounds": max(0, len(history) - 1),
            "trajectory": history,
            "summary": (
                f"Simulação de {count} agentes: tendência de {verdict} "
                f"(consenso {consensus:.2f}, confiança {confidence:.2f}). "
                f"Conceito dominante: '{dominant.name}' ({dominant.stance:.2f})."
            ),
        }


if __name__ == "__main__":
    demo_topology = {
        "nodes": [{"id": "IA"}, {"id": "Redes Neurais"}, {"id": "Dados"}, {"id": "Ética"}],
        "links": [
            {"source": "IA", "target": "Redes Neurais"},
            {"source": "Redes Neurais", "target": "Dados"},
            {"source": "IA", "target": "Ética"},
        ],
    }
    simulator = SwarmSimulator.from_topology(demo_topology, seed=42)
    history = simulator.run(rounds=10)
    print(simulator.report(history)["summary"])
