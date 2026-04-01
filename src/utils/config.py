"""Load and cache YAML config files."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml


CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@functools.lru_cache(maxsize=None)
def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def system_config() -> dict:
    return load_yaml(CONFIG_DIR / "system.yaml")["aks"]


def models_config() -> dict:
    return load_yaml(CONFIG_DIR / "models.yaml")["models"]


def agent_config(name: str) -> dict:
    return load_yaml(CONFIG_DIR / "agents" / f"{name}.yaml")
