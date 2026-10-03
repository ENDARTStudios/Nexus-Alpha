"""Nexus-Alpha — Chain-of-Thought estruturado."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional


@dataclass
class ReasoningStep:
    description: str
    result: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ReasoningTrace:
    goal: str
    steps: list[ReasoningStep] = field(default_factory=list)

    def add(self, step: ReasoningStep) -> None:
        self.steps.append(step)


class ChainOfThought:
    """Decompõe uma requisição em subproblemas antes da resposta final."""

    def __init__(self, solver: Optional[Callable[[str], Awaitable[str]]] = None) -> None:
        self.solver = solver

    async def _run_subproblem(self, subproblem: str) -> ReasoningStep:
        if self.solver is None:
            return ReasoningStep(description=subproblem, result="<aguardando LLM>", confidence=0.0)
        answer = await self.solver(subproblem)
        return ReasoningStep(description=subproblem, result=answer, confidence=0.7)

    async def reason(self, goal: str, subproblems: list[str]) -> ReasoningTrace:
        trace = ReasoningTrace(goal=goal)
        for sub in subproblems:
            step = await self._run_subproblem(sub)
            trace.add(step)
        return trace

    def synthesize(self, trace: ReasoningTrace) -> str:
        if not trace.steps:
            return f"Sem etapas para: {trace.goal}"
        bullets = "\n".join(f"- {s.description}: {s.result}" for s in trace.steps)
        return f"[META] {trace.goal}\n[RACIOCÍNIO]\n{bullets}\n[CONCLUSÃO] {trace.steps[-1].result}"