"""Load and cache YAML config files."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


@functools.lru_cache(maxsize=None)
def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def system_config() -> dict:
    return load_yaml(CONFIG_DIR / "system.yaml")["aks"]


def models_config() -> dict:
    return load_yaml(CONFIG_DIR / "models.yaml")["models"]


def get_provider() -> str:
    return load_yaml(CONFIG_DIR / "models.yaml").get("provider", "gemini")


def agent_config(name: str) -> dict:
    return load_yaml(CONFIG_DIR / "agents" / f"{name}.yaml")
