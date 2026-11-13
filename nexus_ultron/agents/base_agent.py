"""Base Agent Contract and Shared Task Execution Context."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SharedTaskContext:
    """Thread-safe shared blackboard allowing coordinated multi-agent execution within a task."""

    task_id: str
    objective: str
    category: str
    artifacts: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self.artifacts[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self.artifacts.get(key, default)

    def add_note(self, note: str) -> None:
        with self._lock:
            self.notes.append(note)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"artifacts": dict(self.artifacts), "notes": list(self.notes)}


class BaseAgent(ABC):
    """Base class for all built-in and dynamically registered NEXUS ULTRON agents."""

    agent_id: str = "base_agent"
    display_name: str = "Base Agent"
    specialty: str = "General execution"
    heavy_inference: bool = False

    @abstractmethod
    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        """Execute a single subtask and return structured output."""

    def info(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "specialty": self.specialty,
            "heavy_inference": self.heavy_inference,
        }
