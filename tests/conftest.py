"""Shared Pytest Fixtures for the 30-Scenario NEXUS ULTRON Verification Suite."""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Self-heal headless Qt before any PySide6 import: on fresh Linux environments
# missing libGL.so.1/libEGL.so.1/libxkbcommon.so.0/libdbus-1.so.3, compile
# minimal symbol-matched C stubs into .venv/qt_shims/ and point the dynamic
# loader + Qt offscreen plugin at them.
# ---------------------------------------------------------------------------
from nexus_ultron.core.qt_shim_builder import ensure_qt_shims

ensure_qt_shims(Path(__file__).resolve().parent.parent)

import os as _os  # noqa: E402

_os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

from nexus_ultron.runtime import NexusUltronRuntime  # noqa: E402


@pytest.fixture()
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture()
def offline_runtime(tmp_path: Path, repo_root: Path):
    rt = NexusUltronRuntime(
        repo_root=repo_root,
        data_root=tmp_path / "ultron_data",
        simulated_ram_gb=8.0,
        connectivity_probe_fn=lambda: False,
    )
    yield rt
    rt.shutdown()


@pytest.fixture()
def online_runtime(tmp_path: Path, repo_root: Path):
    rt = NexusUltronRuntime(
        repo_root=repo_root,
        data_root=tmp_path / "ultron_online_data",
        simulated_ram_gb=16.0,
        connectivity_probe_fn=lambda: True,
    )
    yield rt
    rt.shutdown()
