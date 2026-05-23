"""
Swarm V4 — Configuration loader.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=32)
def load_yaml_config(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}


def get_env_override(key: str, default: Any = None) -> Any:
    env_key = "SWARM_" + key.upper().replace(".", "_")
    value = os.environ.get(env_key)
    if value is None:
        return default
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def resolve_config(config: dict, key_path: str, default: Any = None) -> Any:
    env_value = get_env_override(key_path)
    if env_value is not None:
        return env_value
    parts = key_path.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current
