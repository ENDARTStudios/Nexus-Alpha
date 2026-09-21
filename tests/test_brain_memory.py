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
    def __init__(self):
        from types import SimpleNamespace

        self.episodic = SimpleNamespace(last_timestamp=lambda: "2026-09-21T00:00:00+00:00")

    def stats(self):
        return {
            "working_active": ["IA"],
            "working_capacity": 7,
            "working_region": "Córtex Pré-Frontal",
            "episodes": 1,
            "episodic_region": "Hipocampo",
            "semantic_region": "Córtex Temporal",
            "min_replays": 3,
            "hebbian_pairs": 0,
        }

    def attend(self, concepts):
        return list(concepts)

    def record_episode(self, kind, content):
        from types import SimpleNamespace

        return SimpleNamespace(timestamp=1.0, kind=kind)

    def consolidation_candidates(self):
        return []

    def recent_episodes(self, limit=20):
        return []

    async def consolidate(self):
        return {"status": "ok", "consolidated": 0}


class FakeBrainFull(FakeBrain):
    def stats(self):
        base = super().stats()
        base.update({"episodes": 24, "hebbian_pairs": 1})
        return base

    def consolidation_candidates(self):
        return [{"subject": "A", "predicate": "DISTRIBUIR", "object": "B", "replays": 5}]

    def recent_episodes(self, limit=20):
        return [{
            "id": "ep_1",
            "created_at": "2026-09-21T00:00:00+00:00",
            "status": "consolidado",
            "replays": 5,
            "subject": "A",
            "predicate": "DISTRIBUIR",
            "object": "B",
        }]


class FakeGraphCounts:
    async def graph_snapshot(self):
        return {
            "concepts": 875,
            "facts": 569,
            "verified": 2,
            "consolidated": 1,
            "hebbian": 4,
            "episodes": 24,
            "last_episode": "2026-09-21T00:00:00+00:00",
        }

    async def recent_episodes(self, limit=20):
        return []

    async def mark_episodes_status(self, fact_hashes, status="consolidado"):
        return len(fact_hashes)

    async def prune_episodes(self, days=30, max_count=10000):
        return 0


class FakeVectorCounts:
    def count(self):
        return 115


def _patch_deps(monkeypatch, brain=None):
    monkeypatch.setattr(app_module, "get_brain", lambda: brain or FakeBrainFull())
    monkeypatch.setattr(app_module, "get_graph_connector", lambda: FakeGraphCounts())
    monkeypatch.setattr(app_module, "get_vector_connector", lambda: FakeVectorCounts())


def test_brain_endpoints(monkeypatch):
    _patch_deps(monkeypatch, FakeBrain())
    client = TestClient(app_module.app)
    assert client.get("/api/brain/stats").status_code == 200
    assert client.post("/api/brain/activate", json={"concepts": ["IA"]}).json()["active"] == ["IA"]
    assert client.post("/api/brain/episode", json={"kind": "t", "concepts": ["IA"]}).status_code == 200
    assert client.post("/api/brain/consolidate").json()["status"] == "ok"


def test_brain_stats_normalized_contract(monkeypatch):
    _patch_deps(monkeypatch)
    body = TestClient(app_module.app).get("/api/brain/stats").json()
    assert set(body) == {"working_memory", "episodic_memory", "consolidation", "graph", "vectors"}
    assert body["working_memory"]["active_slots"] == 1
    assert body["working_memory"]["capacity"] == 7
    assert body["episodic_memory"]["episodes"] == 24
    assert body["episodic_memory"]["last_episode_at"]
    assert body["consolidation"]["candidates"] == 1
    assert body["consolidation"]["consolidated"] == 1
    assert body["consolidation"]["min_replays"] == 3
    assert body["graph"] == {"concepts": 875, "facts": 569, "verified_facts": 2, "hebbian_pairs": 4}
    assert body["vectors"]["count"] == 115


def test_brain_episodes_endpoint(monkeypatch):
    _patch_deps(monkeypatch)
    body = TestClient(app_module.app).get("/api/brain/episodes?limit=5").json()
    assert body["items"][0]["id"] == "ep_1"
    assert body["items"][0]["status"] == "consolidado"


def test_brain_public_payloads_do_not_leak_secrets(monkeypatch):
    _patch_deps(monkeypatch)
    client = TestClient(app_module.app)
    for path in ("/api/brain/stats", "/api/brain/episodes"):
        text = client.get(path).text.lower()
        assert "neo4j" not in text
        assert "password" not in text
        assert "hf_" not in text
        assert "api_key" not in text
        assert "token" not in text


def test_fact_hash_is_stable_and_case_insensitive():
    from src.brain.memory import fact_hash

    a = fact_hash("IA", "UTILIZA", "Dados")
    b = fact_hash(" ia ", "utiliza", " dados ")
    assert a == b
    assert len(a) == 64


def test_episode_payloads_have_fact_hash_day_and_domain(tmp_path):
    from src.brain.memory import BrainMemorySystem, EpisodicMemory

    brain = BrainMemorySystem(episodic=EpisodicMemory(path=tmp_path / "ep.jsonl"))
    payloads = brain.episode_payloads(
        [{"subject": "IA", "predicate": "utiliza", "object": "Dados"}],
        "https://pt.wikipedia.org/wiki/IA",
    )
    assert len(payloads) == 1
    item = payloads[0]
    assert item["predicate"] == "UTILIZA"
    assert item["source_domain"] == "pt.wikipedia.org"
    assert len(item["fact_hash"]) == 64
    assert len(item["day"]) == 10
    assert item["status"] == "novo"


def test_brain_episodes_prefers_durable_store(monkeypatch):
    class DurableGraph(FakeGraphCounts):
        async def recent_episodes(self, limit=20):
            return [{"id": "ep_durable", "status": "consolidado", "replays": 7}]

    monkeypatch.setattr(app_module, "get_brain", lambda: FakeBrain())
    monkeypatch.setattr(app_module, "get_graph_connector", lambda: DurableGraph())
    monkeypatch.setattr(app_module, "get_vector_connector", lambda: FakeVectorCounts())
    body = TestClient(app_module.app).get("/api/brain/episodes").json()
    assert body["source"] == "neo4j"
    assert body["items"][0]["id"] == "ep_durable"


def test_consolidate_reports_retention_and_marks(monkeypatch):
    _patch_deps(monkeypatch)
    body = TestClient(app_module.app).post("/api/brain/consolidate").json()
    assert body["status"] == "ok"
    assert "episodes_marked" in body
    assert "pruned_episodes" in body
