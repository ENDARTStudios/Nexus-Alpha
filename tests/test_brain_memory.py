"""Testes do sistema de memória inspirado no cérebro (working/episódica/semântica)."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.brain import BrainMemorySystem, EpisodicMemory, WorkingMemory
from src.brain.regions import REGIONS, region_for


class FakeGraph:
    def __init__(self) -> None:
        self.calls: list[list[dict]] = []

    async def consolidate_facts(self, facts: list[dict]) -> int:
        self.calls.append(list(facts))
        return len(facts)


def test_working_memory_decay_and_capacity():
    wm = WorkingMemory(capacity=2, decay_seconds=0.05)
    wm.activate("A")
    wm.activate("B")
    wm.activate("C")
    assert len(wm.active()) == 2  # capacidade respeitada
    time.sleep(0.08)
    assert wm.decay() == 2
    assert wm.active() == []


def test_working_memory_focus_returns_last_active():
    wm = WorkingMemory(capacity=5)
    wm.activate("IA")
    wm.activate("DADOS")
    assert wm.focus() == "DADOS"


def test_episodic_record_and_replay(tmp_path):
    em = EpisodicMemory(path=tmp_path / "ep.jsonl")
    em.record("mining", {"x": 1})
    em.record("chat", {"y": 2})
    replay = em.replay()
    assert len(replay) == 2
    assert replay[0]["kind"] == "mining"
    assert em.count() == 2


def test_episodic_prune(tmp_path):
    em = EpisodicMemory(path=tmp_path / "ep.jsonl", max_entries=2)
    for i in range(5):
        em.record("evt", {"i": i})
    assert em.prune() == 3
    assert em.count() == 2


def test_episodic_falls_back_when_preferred_dir_unwritable(tmp_path, monkeypatch):
    blocker = tmp_path / "arquivo_qualquer"
    blocker.write_text("sou um arquivo, nao diretorio", encoding="utf-8")
    monkeypatch.setenv("NEXUS_BRAIN_DIR", str(blocker / "brain"))
    em = EpisodicMemory()
    em.record("t", {"a": 1})
    assert em.count() >= 1
    assert str(blocker) not in str(em.path)
    assert em.path.name == "episodes.jsonl"


def test_consolidation_promotes_repeated_facts(tmp_path):
    brain = BrainMemorySystem(
        episodic=EpisodicMemory(path=tmp_path / "ep.jsonl"), min_replays=2, graph=FakeGraph()
    )
    for _ in range(3):
        brain.record_episode("mining", {"extracted_entities": [
            {"subject": "ia", "predicate": "utiliza", "object": "dados"}
        ]})
    candidates = brain.consolidation_candidates()
    assert candidates == [{"subject": "IA", "predicate": "UTILIZA", "object": "DADOS", "replays": 3}]


@pytest.mark.asyncio
async def test_consolidate_strengthens_and_creates_inverse(tmp_path):
    graph = FakeGraph()
    brain = BrainMemorySystem(
        episodic=EpisodicMemory(path=tmp_path / "ep.jsonl"),
        min_replays=2,
        graph=graph,
        bidirectional=True,
    )
    for _ in range(3):
        brain.record_episode("mining", {"extracted_entities": [
            {"subject": "Pho", "predicate": "pertence_a", "object": "Cachorro"}
        ]})
    report = await brain.consolidate()
    assert report["candidates"] == 1
    assert report["inverses"] == 1
    assert report["consolidated"] == 2
    sent = graph.calls[0]
    assert any(f["predicate"] == "PERTENCE_A" for f in sent)
    assert any(f["predicate"] == "CONTIENE" and f["subject"] == "CACHORRO" for f in sent)


def test_inverse_of_unknown_predicate():
    assert BrainMemorySystem.inverse_of("USA") is None
    assert BrainMemorySystem.inverse_of("pertence_a") == "CONTIENE"
    assert BrainMemorySystem.inverse_of("distribuir") == "DISTRIBUIDO_POR"


def test_brain_stats_exposes_regions(tmp_path):
    brain = BrainMemorySystem(episodic=EpisodicMemory(path=tmp_path / "ep.jsonl"))
    stats = brain.stats()
    assert stats["working_region"] == REGIONS["prefrontal"].name
    assert stats["episodic_region"] == "Hipocampo"
    assert stats["semantic_region"] == "Córtex Temporal"


def test_hebbian_coactivation_counts(tmp_path):
    brain = BrainMemorySystem(episodic=EpisodicMemory(path=tmp_path / "ep.jsonl"))
    brain.attend(["IA", "DADOS"])
    brain.attend(["IA", "DADOS"])
    assert brain.coactivations[("DADOS", "IA")] == 2


def test_region_for_unknown_type_raises():
    with pytest.raises(KeyError):
        region_for("inexistente")


class FakeBrain:
    def stats(self):
        return {"working_active": ["IA"], "episodes": 1}

    def attend(self, concepts):
        return list(concepts)

    def record_episode(self, kind, content):
        from types import SimpleNamespace

        return SimpleNamespace(timestamp=1.0, kind=kind)

    async def consolidate(self):
        return {"status": "ok", "consolidated": 0}


def test_brain_endpoints(monkeypatch):
    monkeypatch.setattr(app_module, "get_brain", lambda: FakeBrain())
    client = TestClient(app_module.app)
    assert client.get("/api/brain/stats").json()["episodes"] == 1
    assert client.post("/api/brain/activate", json={"concepts": ["IA"]}).json()["active"] == ["IA"]
    assert client.post("/api/brain/episode", json={"kind": "t", "concepts": ["IA"]}).status_code == 200
    assert client.post("/api/brain/consolidate").json()["status"] == "ok"
