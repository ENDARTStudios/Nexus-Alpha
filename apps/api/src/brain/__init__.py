"""Nexus-Alpha — Memória inspirada no cérebro humano (working/episódica/semântica)."""
from .memory import (
    INVERSE_PREDICATES,
    BrainMemorySystem,
    Episode,
    EpisodicMemory,
    WorkingMemory,
)
from .regions import REGIONS, Region, region_for

__all__ = [
    "INVERSE_PREDICATES",
    "BrainMemorySystem",
    "Episode",
    "EpisodicMemory",
    "WorkingMemory",
    "REGIONS",
    "Region",
    "region_for",
]
