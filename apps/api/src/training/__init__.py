"""Módulos opt-in para preparação de datasets e configs de fine-tuning.

Este pacote não deve importar torch ou llamafactory em runtime normal.
"""

from .config import DEFAULT_BASE_MODEL, DEFAULT_DATASET_DIR, DEFAULT_DATASET_NAME, build_sft_config, write_sft_config
from .dataset import DEFAULT_DATASET_NAME as DATASET_DEFAULT_NAME, build_dataset, fact_to_alpaca, write_dataset
from .runner import TrainingDependencyMissingError, llamafactory_available, run_train

__all__ = [
    "DEFAULT_BASE_MODEL",
    "DEFAULT_DATASET_DIR",
    "DEFAULT_DATASET_NAME",
    "DATASET_DEFAULT_NAME",
    "TrainingDependencyMissingError",
    "build_dataset",
    "build_sft_config",
    "fact_to_alpaca",
    "llamafactory_available",
    "run_train",
    "write_dataset",
    "write_sft_config",
]
