"""Nexus-Alpha — Taxonomia de regiões cerebrais como namespaces funcionais.

Mapeia estruturas anatômicas reais (referência conceitual dos atlas EBRAINS
Julich-Brain/BigBrain, Allen Human Brain Atlas e Scalable Brain Atlas do INCF)
para os tipos de memória implementados em ``memory.py``.

Nota: aqui **não há cópia de dados** dos atlas — apenas a taxonomia funcional
(região → função → tipo de memória), que é conhecimento científico público.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    key: str
    name: str
    function: str
    memory_type: str


REGIONS: dict[str, Region] = {
    "prefrontal": Region(
        key="prefrontal",
        name="Córtex Pré-Frontal",
        function="Memória de trabalho e controle executivo (foco atencional).",
        memory_type="working",
    ),
    "hippocampus": Region(
        key="hippocampus",
        name="Hipocampo",
        function="Codificação episódica e replay temporal dos eventos.",
        memory_type="episodic",
    ),
    "temporal": Region(
        key="temporal",
        name="Córtex Temporal",
        function="Armazenamento semântico de longo prazo (conceitos e fatos).",
        memory_type="semantic",
    ),
    "sensorimotor": Region(
        key="sensorimotor",
        name="Córtex Sensório-Motor",
        function="Entrada/saída: mineração e ingestão sensorial do mundo.",
        memory_type="sensory",
    ),
    "default_mode": Region(
        key="default_mode",
        name="Rede de Modo Padrão",
        function="Consolidação em repouso ('sono'): replay e promoção de memórias.",
        memory_type="consolidation",
    ),
}


def region_for(memory_type: str) -> Region:
    for region in REGIONS.values():
        if region.memory_type == memory_type:
            return region
    raise KeyError(f"sem região mapeada para o tipo de memória: {memory_type!r}")
