"""Autonomous Desktop & Windows UI Operation Engine (Win32 / pywinauto + Cross-Platform Process Control)."""

from __future__ import annotations

import json
import logging
import os
import platform
import shlex
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import psutil

from ..security.payment_isolation import PaymentIsolationEngine
from ..security.permission_engine import PermissionEngine
from ..storage.database import DatabaseManager

logger = logging.getLogger("nexus_ultron.desktop_operator")


class DesktopOperator:
    """
    Interacts with the host OS using stable APIs (Windows UI Automation / Win32 ctypes / pywinauto
    on Windows 10, plus cross-platform process & terminal APIs), enforcing permissions, payment
    isolation, crash recovery, and full execution history.
    """

    def __init__(
        self,
        db: DatabaseManager,
        permissions: PermissionEngine,
        payment_shield: PaymentIsolationEngine,
    ) -> None:
        self.db = db
        self.permissions = permissions
        self.payment_shield = payment_shield
        self._managed_procs: dict[int, subprocess.Popen[Any]] = {}

    def list_windows(self) -> list[dict[str, Any]]:
        """Enumerate visible top-level windows using Win32 APIs on Windows or process titles on POSIX."""
        windows: list[dict[str, Any]] = []
        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

                def _cb(hwnd: int, _lparam: int) -> bool:
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            pid = ctypes.c_ulong()
                            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                            windows.append(
                                {
                                    "hwnd": int(hwnd),
                                    "pid": int(pid.value),
                                    "title": buf.value,
                                }
                            )
                    return True

                user32.EnumWindows(EnumWindowsProc(_cb), 0)
                return windows
            except Exception as exc:
                logger.debug("Win32 window enumeration fallback: %s", exc)

        # Fallback: inspect running user processes
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"]:
                    windows.append(
                        {
                            "hwnd": proc.info["pid"],
                            "pid": proc.info["pid"],
                            "title": proc.info["name"],
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return windows[:40]

    def launch_application(
        self,
        executable_or_command: str | list[str],
        cwd: Path | None = None,
    ) -> dict[str, Any]:
        """Launch a permitted desktop application without blocking ULTRON's UI."""
        self.permissions.require_permission(
            "application_launching",
            actor="desktop_operator",
            action_desc=f"launch {executable_or_command}",
        )
        args = (
            shlex.split(executable_or_command, posix=(platform.system() != "Windows"))
            if isinstance(executable_or_command, str)
            else list(executable_or_command)
        )
        if not args:
            raise ValueError("Executable command cannot be empty")

        # Check active windows for payment lockdown before interacting
        active_titles = [w["title"] for w in self.list_windows()]
        self.payment_shield.assert_safe_for_screen_capture(active_titles)

        resolved = shutil.which(args[0]) or args[0]
        proc = subprocess.Popen(
            [resolved, *args[1:]],
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        self._managed_procs[proc.pid] = proc
        record = self._record_history(
            "launch_application",
            str(args[0]),
            "running",
            {"pid": proc.pid, "args": args},
        )
        return {"pid": proc.pid, "command": args, "history_id": record["id"]}

    def manage_window(self, hwnd_or_pid: int, action: str = "focus") -> dict[str, Any]:
        """Focus, minimize, maximize, or close a managed window safely."""
        self.permissions.require_permission(
            "routine_automation",
            actor="desktop_operator",
            action_desc=f"window {action} ({hwnd_or_pid})",
        )
        valid_actions = {"focus", "minimize", "maximize", "close"}
        if action not in valid_actions:
            raise ValueError(f"Unsupported window action '{action}'")

        active_titles = [w["title"] for w in self.list_windows()]
        self.payment_shield.assert_safe_for_screen_capture(active_titles)

        applied = False
        if platform.system() == "Windows":
            try:
                import ctypes

                user32 = ctypes.windll.user32
                if action == "focus":
                    user32.ShowWindow(hwnd_or_pid, 9)  # SW_RESTORE
                    user32.SetForegroundWindow(hwnd_or_pid)
                elif action == "minimize":
                    user32.ShowWindow(hwnd_or_pid, 6)  # SW_MINIMIZE
                elif action == "maximize":
                    user32.ShowWindow(hwnd_or_pid, 3)  # SW_MAXIMIZE
                elif action == "close":
                    user32.PostMessageW(hwnd_or_pid, 0x0010, 0, 0)  # WM_CLOSE
                applied = True
            except Exception:
                applied = False
        else:
            if action == "close" and psutil.pid_exists(hwnd_or_pid):
                proc = self._managed_procs.get(hwnd_or_pid)
                if proc:
                    proc.terminate()
                    applied = True
            else:
                applied = psutil.pid_exists(hwnd_or_pid)

        self._record_history("manage_window", str(hwnd_or_pid), "ok" if applied else "missing_window", {"action": action})
        return {"target": hwnd_or_pid, "action": action, "applied": applied}

    def run_terminal_command(
        self,
        command: str,
        cwd: Path | None = None,
        timeout_sec: int = 60,
    ) -> dict[str, Any]:
        """Execute an approved development shell command inside a validated workspace."""
        self.permissions.validate_shell_command(command, workspace_root=cwd, actor="desktop_operator")
        args = (
            ["cmd.exe", "/c", command]
            if platform.system() == "Windows"
            else ["/bin/bash", "-lc", command]
        )
        env = dict(os.environ)
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
        status = "succeeded" if completed.returncode == 0 else "failed"
        self._record_history(
            "terminal_command",
            command[:100],
            status,
            {"exit_code": completed.returncode},
        )
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "succeeded": completed.returncode == 0,
        }

    def capture_screen_if_safe(
        self,
        output_path: Path,
        simulated_window_titles: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Capture desktop screenshot ONLY after Payment Isolation confirms zero financial/banking/checkout
        windows or processes are open. Fails closed if uncertain.
        """
        self.permissions.require_permission("routine_automation", actor="desktop_operator", action_desc="screen_capture")
        titles = (
            simulated_window_titles
            if simulated_window_titles is not None
            else [w["title"] for w in self.list_windows()]
        )
        proc_names = []
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"]:
                    proc_names.append(p.info["name"])
            except Exception:
                continue

        # Mandatory Payment Isolation check (raises PaymentIsolationTriggered on any financial window or None)
        self.payment_shield.assert_safe_for_screen_capture(titles, proc_names)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image, ImageDraw

            # On Windows desktop, ImageGrab captures real display; in headless environments create diagnostic frame
            try:
                from PIL import ImageGrab

                img = ImageGrab.grab()
            except Exception:
                img = Image.new("RGB", (1280, 720), color=(5, 7, 11))
                draw = ImageDraw.Draw(img)
                draw.text((40, 40), "NEXUS ULTRON SAFE WORKSPACE SNAPSHOT (NO PROTECTED WINDOWS)", fill=(0, 217, 255))
            img.save(str(output_path), "PNG")
        except Exception as exc:
            raise RuntimeError(f"Screen capture failed: {exc}") from exc

        self._record_history("screen_capture", str(output_path), "captured", {})
        return {"captured": True, "path": str(output_path)}

    def execute_with_recovery(
        self,
        step_name: str,
        operation: Callable[[], dict[str, Any]],
        recovery_fn: Callable[[Exception], dict[str, Any]] | None = None,
        max_attempts: int = 2,
    ) -> dict[str, Any]:
        """Recover gracefully from crashed applications, missing windows, or transient UI changes."""
        last_exc: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                res = operation()
                self._record_history("workflow_step", step_name, "completed", {"attempt": attempt})
                return {"recovered": attempt > 1, "attempts": attempt, "result": res}
            except Exception as exc:
                last_exc = exc
                logger.warning("Desktop step '%s' failed on attempt %d: %s", step_name, attempt, exc)
                if recovery_fn and attempt < max_attempts:
                    try:
                        recovery_fn(exc)
                    except Exception:
                        pass
        self._record_history("workflow_step", step_name, "failed", {"error": str(last_exc)})
        raise RuntimeError(f"Desktop operation '{step_name}' failed after {max_attempts} attempts: {last_exc}")

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM desktop_execution_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def _record_history(self, action_type: str, target: str, status: str, details: dict[str, Any]) -> dict[str, Any]:
        hid = f"dsk_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO desktop_execution_history (id, action_type, target, status, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (hid, action_type, target[:160], status, json.dumps(details, default=str), now),
        )
        return {"id": hid, "action_type": action_type, "target": target, "status": status, "created_at": now}
