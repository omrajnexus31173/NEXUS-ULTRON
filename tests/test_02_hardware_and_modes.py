"""QA Scenarios #3, #4, #5, #6, #28: Offline/Online Startup, Disconnect, Mode Switching & 8GB Low-Memory Mode."""

from __future__ import annotations

from pathlib import Path

from nexus_ultron.core.connectivity import ConnectivityManager
from nexus_ultron.core.hardware import detect_hardware_profile
from nexus_ultron.runtime import NexusUltronRuntime


def test_hardware_tiers_8gb_12gb_16gb_32gb(tmp_path: Path) -> None:
    """Verify automatic hardware tiering across 8 GB, 12 GB, 16 GB, and 32 GB+ targets."""
    assert detect_hardware_profile(tmp_path, simulated_ram_gb=8.0).tier == "lightweight"
    assert detect_hardware_profile(tmp_path, simulated_ram_gb=12.0).tier == "balanced"
    assert detect_hardware_profile(tmp_path, simulated_ram_gb=16.0).tier == "enhanced"
    assert detect_hardware_profile(tmp_path, simulated_ram_gb=32.0).tier == "high_performance"


def test_03_04_05_06_offline_online_disconnect_and_antiflap_switching(
    offline_runtime: NexusUltronRuntime,
    online_runtime: NexusUltronRuntime,
) -> None:
    """Tests #3 (Offline startup), #4 (Online startup), #5 (Disconnection) & #6 (Mode switching + anti-flap)."""
    assert offline_runtime.connectivity.effective_mode == "offline"
    assert online_runtime.connectivity.effective_mode == "online"

    # Anti-flap test: a single transient network blip must NOT flip mode when flap_threshold=2
    net_up = {"state": True}
    cm = ConnectivityManager(initial_policy="automatic", flap_threshold=2, probe_fn=lambda: net_up["state"])
    assert cm.effective_mode == "online"

    net_up["state"] = False
    cm.refresh(force_immediate=False)
    assert cm.effective_mode == "online"  # Still online on 1st transient drop!

    cm.refresh(force_immediate=False)
    assert cm.effective_mode == "offline"  # Cleanly switches to offline on 2nd consecutive drop!

    # Manual offline mode stays offline even if internet returns
    net_up["state"] = True
    cm.set_policy("manual_offline")
    assert cm.effective_mode == "offline"

    # Manual online degrades safely to offline if internet is completely unreachable (never crashes)
    net_up["state"] = False
    st = cm.set_policy("manual_online")
    assert st["effective_mode"] == "offline"
    assert st["manual_online_degraded"] is True


def test_28_low_memory_behavior_graceful_degradation(offline_runtime: NexusUltronRuntime) -> None:
    """Test #28: Under simulated RAM exhaustion on an 8 GB machine, ULTRON throttles concurrency safely."""
    normal_snap = offline_runtime.resources.snapshot()
    assert normal_snap["tier"] == "lightweight"
    assert offline_runtime.config.get("preload_llm_on_startup") is False

    offline_runtime.resources.set_simulated_low_memory(True)
    low_snap = offline_runtime.resources.snapshot()
    assert low_snap["low_memory_mode_active"] is True
    assert low_snap["recommended_parallel_workers"] == 1
    assert low_snap["recommended_local_llm_slots"] == 0

    # Tasks still complete safely via single-worker queueing without crashing
    res = offline_runtime.orchestrator.run_objective_sync("Run diagnostic under low memory")
    assert res["state"] == "Completed" and res["verified"] is True
    offline_runtime.resources.set_simulated_low_memory(False)
