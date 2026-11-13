"""System monitoring and intelligent resource manager (psutil + low-memory degradation)."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

from .hardware import HardwareProfile

logger = logging.getLogger("nexus_ultron.resources")


class ResourceManager:
    """
    Monitors CPU, RAM, storage, battery, network, and processes, and enforces
    adaptive concurrency limits, memory-leak tracking, and temporary-file cleanup.
    """

    def __init__(self, hardware: HardwareProfile, temp_dir: Path) -> None:
        self.hardware = hardware
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._process = psutil.Process(os.getpid())
        self._rss_samples_mb: deque[tuple[float, float]] = deque(maxlen=60)
        self._simulated_low_memory: bool = False
        self._lock = threading.Lock()
        # Prime non-blocking CPU percent measurement
        psutil.cpu_percent(interval=None)

    def set_simulated_low_memory(self, enabled: bool) -> None:
        """Testing hook for deterministic verification of 8GB low-memory graceful degradation."""
        with self._lock:
            self._simulated_low_memory = enabled

    def snapshot(self) -> dict[str, Any]:
        """Return live telemetry for dashboard & adaptive scheduler."""
        vm = psutil.virtual_memory()
        cpu_pct = psutil.cpu_percent(interval=None)
        disk_target = str(self.temp_dir if self.temp_dir.exists() else Path.cwd())
        disk = psutil.disk_usage(disk_target)
        net = psutil.net_io_counters()
        batt = None
        try:
            batt = psutil.sensors_battery()
        except Exception:
            batt = None

        app_rss_mb = round(self._process.memory_info().rss / (1024 * 1024), 2)
        now_ts = time.time()
        with self._lock:
            self._rss_samples_mb.append((now_ts, app_rss_mb))
            sim_low = self._simulated_low_memory

        ram_pct = 92.5 if sim_low else vm.percent
        low_mem_active = ram_pct >= self.hardware.low_memory_guard_percent

        # Adaptive concurrency: throttle down to 1 worker under memory pressure
        recommended_workers = 1 if low_mem_active else self.hardware.max_parallel_agents
        recommended_llm_slots = 0 if sim_low else (
            1 if low_mem_active else self.hardware.max_local_llm_concurrency
        )

        battery_info = {
            "present": batt is not None,
            "percent": round(batt.percent, 1) if batt else 100.0,
            "power_plugged": bool(batt.power_plugged) if batt else True,
            "status_label": (
                f"{round(batt.percent)}% ({'Charging/AC' if batt.power_plugged else 'On Battery'})"
                if batt
                else "AC Power / Desktop"
            ),
        }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": self.hardware.tier,
            "tier_label": self.hardware.tier_label,
            "cpu_percent": round(cpu_pct, 1),
            "ram_percent": round(ram_pct, 1),
            "ram_used_gb": round((vm.total - vm.available) / (1024**3), 2),
            "ram_available_gb": 0.45 if sim_low else round(vm.available / (1024**3), 2),
            "ram_total_gb": self.hardware.total_ram_gb,
            "storage_free_gb": round(disk.free / (1024**3), 2),
            "storage_total_gb": round(disk.total / (1024**3), 2),
            "storage_percent": round(disk.percent, 1),
            "battery": battery_info,
            "network": {
                "bytes_sent_mb": round(net.bytes_sent / (1024 * 1024), 2) if net else 0.0,
                "bytes_recv_mb": round(net.bytes_recv / (1024 * 1024), 2) if net else 0.0,
            },
            "app_rss_mb": app_rss_mb,
            "low_memory_mode_active": low_mem_active,
            "recommended_parallel_workers": recommended_workers,
            "recommended_local_llm_slots": recommended_llm_slots,
            "memory_leak_warning": self._check_memory_growth(),
        }

    def _check_memory_growth(self) -> bool:
        with self._lock:
            if len(self._rss_samples_mb) < 10:
                return False
            first_mb = self._rss_samples_mb[0][1]
            last_mb = self._rss_samples_mb[-1][1]
        # Warn if process grew by > 450 MB within recent window
        return (last_mb - first_mb) > 450.0

    def list_top_processes(self, limit: int = 12) -> list[dict[str, Any]]:
        procs: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
            try:
                info = proc.info
                mem_mb = round((info["memory_info"].rss if info["memory_info"] else 0) / (1024 * 1024), 1)
                procs.append(
                    {
                        "pid": info["pid"],
                        "name": info["name"] or "unknown",
                        "cpu_percent": round(info["cpu_percent"] or 0.0, 1),
                        "memory_mb": mem_mb,
                        "status": info["status"] or "running",
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        procs.sort(key=lambda item: (item["memory_mb"], item["cpu_percent"]), reverse=True)
        return procs[:limit]

    def cleanup_temp_files(self, max_age_hours: float = 24.0) -> int:
        """Delete stale temporary files inside ULTRON's temp folder."""
        if not self.temp_dir.exists():
            return 0
        removed = 0
        cutoff = time.time() - (max_age_hours * 3600.0)
        for item in self.temp_dir.rglob("*"):
            if item.is_file():
                try:
                    if item.stat().st_mtime <= cutoff:
                        item.unlink()
                        removed += 1
                except OSError:
                    continue
        return removed
