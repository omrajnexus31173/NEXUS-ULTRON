"""Unified CLI, Native PySide6 Desktop Launcher & Live Web Command Center Entrypoint."""

from __future__ import annotations

import argparse
import json
import os as _os
import sys
from pathlib import Path

# Self-heal headless Qt shims before any PySide6 import (fresh Linux envs
# missing libGL.so.1/libEGL.so.1/libxkbcommon.so.0/libdbus-1.so.3).
from .core.qt_shim_builder import ensure_qt_shims  # noqa: E402

ensure_qt_shims(Path(__file__).resolve().parent.parent.parent)
# Only force offscreen platform on headless Linux; on Windows let Qt use the native Windows plugin.
if sys.platform == "linux":
    _os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import uvicorn  # noqa: E402

from .runtime import NexusUltronRuntime  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nexus-ultron",
        description="NEXUS ULTRON — Autonomous Personal AI Operating System",
    )
    parser.add_argument("--desktop", action="store_true", help="Launch PySide6 Native Desktop Dashboard (default on Windows)")
    parser.add_argument("--web", action="store_true", help="Launch Web Command Center server")
    parser.add_argument("--host", default="0.0.0.0", help="Web server bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Web server bind port (default: 8765)")
    parser.add_argument("--health-check", action="store_true", help="Run non-interactive system & security health check")
    parser.add_argument("--objective", type=str, default=None, help="Execute a single autonomous objective from CLI and print verified result")
    parser.add_argument("--data-dir", type=str, default=None, help="Custom user_data directory path")

    args = parser.parse_args(argv)
    data_root = Path(args.data_dir) if args.data_dir else None
    runtime = NexusUltronRuntime(data_root=data_root)

    if args.health_check:
        overview = runtime.dashboard_overview()
        audit_ok, audit_count = runtime.audit.verify_integrity()
        health = {
            "status": "HEALTHY",
            "version": overview["version"],
            "hardware_tier": overview["hardware"]["tier_label"],
            "mode": overview["connectivity"]["effective_mode"],
            "audit_chain_valid": audit_ok,
            "audit_entries": audit_count,
            "chrome_isolation_verified": runtime.browser.get_chrome_isolation_status()["user_chrome_untouched"],
            "registered_agents": overview["orchestrator"]["registered_agent_count"],
            "registered_skills": len(runtime.plugins.list_skills()),
        }
        print(json.dumps(health, indent=2))
        runtime.shutdown()
        return 0

    if args.objective:
        result = runtime.orchestrator.run_objective_sync(
            objective=args.objective,
            mode_used=runtime.connectivity.effective_mode,
        )
        print(json.dumps(result, indent=2))
        runtime.shutdown()
        return 0 if result["verified"] else 1

    if args.web and not args.desktop:
        from .web_ui.server import create_web_app

        web_app = create_web_app(runtime)
        uvicorn.run(web_app, host=args.host, port=args.port, log_level="info")
        return 0

    # Default: Launch Native PySide6 Desktop Application
    from PySide6.QtWidgets import QApplication
    from .desktop_ui.main_window import NexusUltronMainWindow

    qt_app = QApplication(sys.argv)
    win = NexusUltronMainWindow(runtime)
    win.show()
    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
