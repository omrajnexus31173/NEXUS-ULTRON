"""Configuration management with schema validation and corrupted-config recovery."""

from __future__ import annotations

import copy
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("nexus_ultron.config")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = copy.deepcopy(v)
    return merged


class ConfigManager:
    """Manages default and user configuration with automatic corruption recovery."""

    def __init__(self, default_config_path: Path, user_config_path: Path) -> None:
        self.default_config_path = Path(default_config_path)
        self.user_config_path = Path(user_config_path)
        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        self._defaults: dict[str, Any] = self._load_defaults()
        self.recovered_from_corruption: bool = False
        self._config: dict[str, Any] = self.load()

    def _load_defaults(self) -> dict[str, Any]:
        if self.default_config_path.exists():
            return json.loads(self.default_config_path.read_text(encoding="utf-8"))
        return {
            "app_name": "NEXUS ULTRON",
            "version": "3.0.0",
            "mode_policy": "automatic",
            "preload_llm_on_startup": False,
        }

    def load(self) -> dict[str, Any]:
        if not self.user_config_path.exists():
            merged = copy.deepcopy(self._defaults)
            self._atomic_write(merged)
            return merged
        try:
            raw = self.user_config_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ValueError("Root config must be a JSON object")
            merged = _deep_merge(self._defaults, parsed)
            # Enforce mandatory safety invariant: never preload heavy LLMs at startup
            merged["preload_llm_on_startup"] = False
            self._config = merged
            return merged
        except Exception as exc:
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self.user_config_path.with_name(f"config.corrupted.{ts}.bak")
            try:
                shutil.copy2(self.user_config_path, backup)
            except Exception:
                pass
            logger.warning(
                "Corrupted user configuration detected (%s); backed up to %s and restored safe defaults.",
                exc,
                backup.name,
            )
            self.recovered_from_corruption = True
            merged = copy.deepcopy(self._defaults)
            self._atomic_write(merged)
            self._config = merged
            return merged

    def _atomic_write(self, data: dict[str, Any]) -> None:
        tmp_path = self.user_config_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp_path.replace(self.user_config_path)

    def get(self, dotted_key: str, default: Any = None) -> Any:
        node: Any = self._config
        for part in dotted_key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def set(self, dotted_key: str, value: Any) -> None:
        parts = dotted_key.split(".")
        node = self._config
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        # Maintain safety invariants
        if dotted_key == "preload_llm_on_startup":
            self._config["preload_llm_on_startup"] = False
        self._atomic_write(self._config)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)
