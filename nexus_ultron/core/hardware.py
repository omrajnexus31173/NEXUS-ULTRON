"""Automatic hardware detection and adaptive tier configuration (8GB / 12GB / 16GB / 32GB+)."""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    os_release: str
    os_version: str
    is_windows: bool
    is_64bit: bool
    architecture: str
    cpu_logical_cores: int
    cpu_physical_cores: int
    total_ram_gb: float
    available_ram_gb: float
    storage_total_gb: float
    storage_free_gb: float
    has_dedicated_gpu: bool
    gpu_name: str
    tier: str
    tier_label: str
    max_parallel_agents: int
    max_local_llm_concurrency: int
    memory_cache_mb: int
    lazy_load_modules: bool
    low_memory_guard_percent: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_gpu() -> tuple[bool, str]:
    """Detect optional GPU without requiring CUDA or proprietary drivers."""
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        return True, "NVIDIA GPU (nvidia-smi detected)"
    if platform.system() == "Windows":
        # Lightweight environment check without blocking WMI calls if unavailable
        gpu_env = os.environ.get("NEXUS_DETECTED_GPU", "")
        if gpu_env:
            return True, gpu_env
    return False, "Integrated / CPU Execution Mode (No Dedicated GPU Required)"


def classify_hardware_tier(total_ram_gb: float, cpu_cores: int) -> dict[str, Any]:
    """
    Map detected RAM & CPU to the four required NEXUS ULTRON compatibility modes:
      - < 12 GB (8 GB baseline target): Lightweight mode
      - 12 GB to < 16 GB: Balanced mode
      - 16 GB to < 32 GB: Enhanced mode
      - >= 32 GB: High-performance mode
    """
    if total_ram_gb >= 31.0:
        return {
            "tier": "high_performance",
            "tier_label": "High-Performance Mode (32 GB+ RAM)",
            "max_parallel_agents": min(16, max(6, cpu_cores * 2)),
            "max_local_llm_concurrency": 4,
            "memory_cache_mb": 512,
            "lazy_load_modules": True,
            "low_memory_guard_percent": 88.0,
        }
    if total_ram_gb >= 15.5:
        return {
            "tier": "enhanced",
            "tier_label": "Enhanced Mode (16 GB RAM)",
            "max_parallel_agents": min(8, max(4, cpu_cores)),
            "max_local_llm_concurrency": 2,
            "memory_cache_mb": 256,
            "lazy_load_modules": True,
            "low_memory_guard_percent": 85.0,
        }
    if total_ram_gb >= 11.5:
        return {
            "tier": "balanced",
            "tier_label": "Balanced Mode (12 GB RAM)",
            "max_parallel_agents": min(5, max(3, cpu_cores)),
            "max_local_llm_concurrency": 1,
            "memory_cache_mb": 128,
            "lazy_load_modules": True,
            "low_memory_guard_percent": 83.0,
        }
    return {
        "tier": "lightweight",
        "tier_label": "Lightweight Mode (8 GB Baseline Target)",
        "max_parallel_agents": min(3, max(2, cpu_cores // 2 or 2)),
        "max_local_llm_concurrency": 1,
        "memory_cache_mb": 64,
        "lazy_load_modules": True,
        "low_memory_guard_percent": 80.0,
    }


def detect_hardware_profile(
    storage_path: Path | None = None,
    simulated_ram_gb: float | None = None,
    override_tier: str | None = None,
) -> HardwareProfile:
    """Inspect host hardware and return an auto-configured HardwareProfile."""
    vm = psutil.virtual_memory()
    target_path = Path(storage_path or Path.cwd())
    if not target_path.exists():
        target_path = Path.cwd()
    disk = psutil.disk_usage(str(target_path))

    logical_cores = psutil.cpu_count(logical=True) or 2
    physical_cores = psutil.cpu_count(logical=False) or max(1, logical_cores // 2)

    total_ram_gb = round(
        simulated_ram_gb if simulated_ram_gb is not None else (vm.total / (1024**3)),
        2,
    )
    avail_ram_gb = round(
        min(total_ram_gb, vm.available / (1024**3)),
        2,
    )
    has_gpu, gpu_name = _detect_gpu()

    tier_map = {
        "lightweight": 8.0,
        "balanced": 12.0,
        "enhanced": 16.0,
        "high_performance": 32.0,
    }
    effective_ram = tier_map.get(override_tier or "", total_ram_gb)
    tier_cfg = classify_hardware_tier(effective_ram, logical_cores)

    arch = platform.machine() or "AMD64"
    is_64bit = arch.lower() in {"amd64", "x86_64", "arm64", "aarch64"} or (os.sys.maxsize > 2**32)

    return HardwareProfile(
        os_name=platform.system(),
        os_release=platform.release(),
        os_version=platform.version(),
        is_windows=(platform.system() == "Windows"),
        is_64bit=is_64bit,
        architecture=arch,
        cpu_logical_cores=logical_cores,
        cpu_physical_cores=physical_cores,
        total_ram_gb=total_ram_gb,
        available_ram_gb=avail_ram_gb,
        storage_total_gb=round(disk.total / (1024**3), 2),
        storage_free_gb=round(disk.free / (1024**3), 2),
        has_dedicated_gpu=has_gpu,
        gpu_name=gpu_name,
        tier=tier_cfg["tier"],
        tier_label=tier_cfg["tier_label"],
        max_parallel_agents=tier_cfg["max_parallel_agents"],
        max_local_llm_concurrency=tier_cfg["max_local_llm_concurrency"],
        memory_cache_mb=tier_cfg["memory_cache_mb"],
        lazy_load_modules=tier_cfg["lazy_load_modules"],
        low_memory_guard_percent=tier_cfg["low_memory_guard_percent"],
    )
