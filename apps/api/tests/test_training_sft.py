"""Testes unitários para o módulo opt-in de fine-tuning LlamaFactory.

Estes testes não importam torch nem llamafactory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import train_lora  # noqa: E402

from src.training import config as training_config  # noqa: E402
from src.training import dataset as training_dataset  # noqa: E402
from src.training import runner as training_runner  # noqa: E402


SAMPLE_FACT = {
    "subject": "Santos FC",
    "predicate": "FOUNDED_IN",
    "object": "1912",
    "verified": True,
    "confirmations": 3,
    "source_domains": ["almanaquedosclubes.com", "pt.wikipedia.org", "fifa.com"],
}


def test_fact_to_alpaca_basic():
    record = training_dataset.fact_to_alpaca(SAMPLE_FACT)

    assert record is not None
    assert set(record.keys()) == {"instruction", "input", "output"}
    assert "Santos FC" in record["instruction"]
    assert "1912" in record["instruction"]
    assert "FOUNDED_IN" in record["input"]
    assert "almanaquedosclubes.com" in record["input"]
    assert record["output"].startswith("Santos FC FOUNDED_IN 1912.")
    assert "3 fontes independentes" in record["output"]


def test_fact_to_alpaca_skips_unverified_and_incomplete():
    assert (
        training_dataset.fact_to_alpaca(
            {"subject": "A", "predicate": "R", "object": "B", "verified": False}
        )
        is None
    )
    assert training_dataset.fact_to_alpaca({"subject": "A", "predicate": "R"}) is None
    assert training_dataset.fact_to_alpaca("not-a-dict") is None


def test_build_dataset_returns_records_and_info():
    records, info = training_dataset.build_dataset(
        [SAMPLE_FACT, {"subject": "", "predicate": "", "object": ""}]
    )

    assert len(records) == 1
    assert "nexus_verified_facts" in info
    assert info["nexus_verified_facts"]["file_name"] == "nexus_verified_facts.jsonl"
    assert info["nexus_verified_facts"]["columns"] == {
        "prompt": "instruction",
        "query": "input",
        "response": "output",
    }


def test_write_dataset_creates_jsonl_and_dataset_info(tmp_path):
    result = training_dataset.write_dataset(tmp_path / "sft", [SAMPLE_FACT])

    jsonl_path = Path(result["jsonl_path"])
    info_path = Path(result["dataset_info_path"])

    assert jsonl_path.exists()
    assert info_path.exists()
    assert result["records"] == 1

    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    record = json.loads(lines[0])
    assert record["instruction"]
    assert record["input"]
    assert record["output"]

    info = json.loads(info_path.read_text(encoding="utf-8"))
    assert "nexus_verified_facts" in info


def test_write_dataset_merges_existing_dataset_info(tmp_path):
    out_dir = tmp_path / "sft"
    out_dir.mkdir()

    info_path = out_dir / "dataset_info.json"
    info_path.write_text(
        json.dumps({"existing_dataset": {"file_name": "existing.jsonl"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    training_dataset.write_dataset(out_dir, [SAMPLE_FACT])

    info = json.loads(info_path.read_text(encoding="utf-8"))
    assert "existing_dataset" in info
    assert "nexus_verified_facts" in info


def test_build_sft_config_defaults():
    cfg = training_config.build_sft_config()

    assert cfg["model_name_or_path"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert cfg["stage"] == "sft"
    assert cfg["finetuning_type"] == "lora"
    assert cfg["template"] == "qwen"
    assert cfg["dataset"] == "nexus_verified_facts"
    assert cfg["dataset_dir"] == "data/sft"
    assert cfg["output_dir"] == "saves/nexus-lora"
    assert cfg["fp16"] is True
    assert cfg["bf16"] is False
    assert "max_samples" not in cfg


def test_write_sft_config_valid_yaml(tmp_path):
    path = training_config.write_sft_config(tmp_path / "sft_lora.yaml")

    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert loaded["stage"] == "sft"
    assert loaded["dataset"] == "nexus_verified_facts"
    assert loaded["dataset_dir"] == "data/sft"


def test_llamafactory_available_false_when_missing(monkeypatch):
    monkeypatch.setattr(training_runner.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(training_runner.shutil, "which", lambda cmd: None)

    assert training_runner.llamafactory_available() is False


def test_run_train_missing_dependency_raises_friendly_error(tmp_path, monkeypatch):
    config_path = tmp_path / "sft_lora.yaml"
    config_path.write_text("stage: sft\n", encoding="utf-8")

    monkeypatch.setattr(training_runner.importlib.util, "find_spec", lambda name: None)
    monkeypatch.setattr(training_runner.shutil, "which", lambda cmd: None)

    with pytest.raises(
        training_runner.TrainingDependencyMissingError,
        match="LlamaFactory não está instalado",
    ):
        training_runner.run_train(config_path)


def test_cli_export_from_file_to_tmp(tmp_path, capsys):
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(
        json.dumps([SAMPLE_FACT], ensure_ascii=False), encoding="utf-8"
    )

    out_dir = tmp_path / "sft"

    rc = train_lora.main(
        [
            "export",
            "--source",
            "file",
            "--file",
            str(facts_path),
            "--out-dir",
            str(out_dir),
            "--limit",
            "10",
        ]
    )

    assert rc == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["records"] == 1
    assert Path(payload["jsonl_path"]).exists()
    assert Path(payload["dataset_info_path"]).exists()


def test_generated_training_artifacts_do_not_leak_secrets(tmp_path):
    facts_path = tmp_path / "facts.json"
    facts_path.write_text(
        json.dumps([SAMPLE_FACT], ensure_ascii=False), encoding="utf-8"
    )

    out_dir = tmp_path / "sft"
    train_lora.main(
        [
            "export",
            "--source",
            "file",
            "--file",
            str(facts_path),
            "--out-dir",
            str(out_dir),
        ]
    )

    config_path = training_config.write_sft_config(tmp_path / "sft_lora.yaml")

    forbidden = [
        "hf_",
        "neo4j",
        "password",
        "NEXUS_API_TOKEN",
        "HF_TOKEN",
        "NEO4J_PASSWORD",
        "Authorization",
        "X-Nexus-Token",
    ]

    paths = [
        out_dir / "nexus_verified_facts.jsonl",
        out_dir / "dataset_info.json",
        config_path,
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in forbidden:
            assert (
                token.lower() not in lowered
            ), f"Segredo/padrão proibido '{token}' encontrado em {path.name}"
