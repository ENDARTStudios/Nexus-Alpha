"""Geração de configuração LoRA/SFT compatível com LlamaFactory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
DEFAULT_TEMPLATE = "qwen"
DEFAULT_DATASET_NAME = "nexus_verified_facts"
DEFAULT_DATASET_DIR = "data/sft"
DEFAULT_OUTPUT_DIR = "saves/nexus-lora"


def build_sft_config(
    *,
    base_model: str = DEFAULT_BASE_MODEL,
    template: str = DEFAULT_TEMPLATE,
    dataset_name: str = DEFAULT_DATASET_NAME,
    dataset_dir: str = DEFAULT_DATASET_DIR,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    epochs: float = 3.0,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    learning_rate: float = 5.0e-5,
    lora_rank: int = 8,
    lora_alpha: int = 16,
    lora_dropout: float = 0.05,
    lora_target: str = "all",
    cutoff_len: int = 1024,
    fp16: bool = True,
    bf16: bool = False,
    logging_steps: int = 10,
    save_steps: int = 50,
    save_total_limit: int = 2,
    warmup_ratio: float = 0.1,
    max_samples: int = 0,
) -> dict[str, Any]:
    """Monta dict de configuração SFT/LoRA para LlamaFactory."""
    config: dict[str, Any] = {
        "model_name_or_path": base_model,
        "stage": "sft",
        "do_train": True,
        "finetuning_type": "lora",
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "lora_target": lora_target,
        "template": template,
        "dataset": dataset_name,
        "dataset_dir": dataset_dir,
        "output_dir": output_dir,
        "overwrite_output_dir": True,
        "per_device_train_batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "num_train_epochs": epochs,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": warmup_ratio,
        "logging_steps": logging_steps,
        "save_steps": save_steps,
        "save_total_limit": save_total_limit,
        "fp16": fp16,
        "bf16": bf16,
        "report_to": "none",
        "plot_loss": True,
        "cutoff_len": cutoff_len,
        "preprocessing_num_workers": 1,
        "dataloader_num_workers": 0,
    }

    if max_samples and max_samples > 0:
        config["max_samples"] = max_samples

    return config


def write_sft_config(
    path: str | Path,
    config: dict[str, Any] | None = None,
    **overrides: Any,
) -> Path:
    """Grava configuração YAML. Se `config` for None, usa `build_sft_config(**overrides)`."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if config is None:
        config = build_sft_config(**overrides)
    elif overrides:
        config = {**config, **overrides}

    target.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return target
