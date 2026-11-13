"""Hybrid Offline/Online connectivity detection and anti-flapping mode switching."""

from __future__ import annotations

import logging
import socket
import threading
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger("nexus_ultron.connectivity")

VALID_POLICIES = {"automatic", "manual_offline", "manual_online"}


class ConnectivityManager:
    """
    Manages Automatic, Manual Offline, and Manual Online modes with anti-flap hysteresis.
    Never crashes when network or cloud endpoints are unreachable.
    """

    def __init__(
        self,
        initial_policy: str = "automatic",
        flap_threshold: int = 2,
        probe_fn: Callable[[], bool] | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._policy = initial_policy if initial_policy in VALID_POLICIES else "automatic"
        self._flap_threshold = max(1, flap_threshold)
        self._probe_fn = probe_fn or self._default_probe
        self._internet_reachable: bool = False
        self._effective_mode: str = "offline"
        self._consecutive_diff: int = 0
        self._last_checked_at: str | None = None
        self._transition_history: list[dict[str, Any]] = []
        self._listeners: list[Callable[[str, str], None]] = []

        # Run initial check immediately (without anti-flap delay on startup)
        self.refresh(force_immediate=True)

    @staticmethod
    def _default_probe() -> bool:
        """Fast non-blocking TCP/HTTPS reachability check against permitted endpoints."""
        endpoints = [
            ("api.github.com", 443),
            ("pypi.org", 443),
            ("1.1.1.1", 443),
        ]
        for host, port in endpoints:
            try:
                with socket.create_connection((host, port), timeout=1.5):
                    return True
            except OSError:
                continue
        return False

    def set_probe_fn(self, probe_fn: Callable[[], bool]) -> None:
        with self._lock:
            self._probe_fn = probe_fn

    def add_listener(self, callback: Callable[[str, str], None]) -> None:
        with self._lock:
            self._listeners.append(callback)

    @property
    def policy(self) -> str:
        with self._lock:
            return self._policy

    @property
    def effective_mode(self) -> str:
        with self._lock:
            return self._effective_mode

    @property
    def internet_reachable(self) -> bool:
        with self._lock:
            return self._internet_reachable

    def set_policy(self, policy: str) -> dict[str, Any]:
        if policy not in VALID_POLICIES:
            raise ValueError(f"Invalid mode policy '{policy}'. Expected one of {sorted(VALID_POLICIES)}")
        with self._lock:
            self._policy = policy
            self._consecutive_diff = 0
        return self.refresh(force_immediate=True)

    def report_connection_failure(self, service_name: str) -> dict[str, Any]:
        """Called by cloud providers on network error to trigger safe local fallback."""
        logger.warning("Connection failure reported by '%s'; verifying connectivity.", service_name)
        return self.refresh(force_immediate=True, simulated_reachable=False)

    def refresh(self, force_immediate: bool = False, simulated_reachable: bool | None = None) -> dict[str, Any]:
        try:
            reachable = simulated_reachable if simulated_reachable is not None else bool(self._probe_fn())
        except Exception as exc:
            logger.debug("Connectivity probe exception safely handled: %s", exc)
            reachable = False

        notify_args: tuple[str, str] | None = None
        with self._lock:
            prev_mode = self._effective_mode
            self._last_checked_at = datetime.now(timezone.utc).isoformat()

            if force_immediate:
                self._internet_reachable = reachable
                self._consecutive_diff = 0
            else:
                if reachable != self._internet_reachable:
                    self._consecutive_diff += 1
                    if self._consecutive_diff >= self._flap_threshold:
                        self._internet_reachable = reachable
                        self._consecutive_diff = 0
                else:
                    self._consecutive_diff = 0

            if self._policy == "manual_offline":
                desired_mode = "offline"
            elif self._policy == "manual_online":
                # If user selects manual_online but internet is completely down, fall back safely
                desired_mode = "online" if self._internet_reachable else "offline"
            else:
                desired_mode = "online" if self._internet_reachable else "offline"

            if desired_mode != prev_mode:
                self._effective_mode = desired_mode
                event = {
                    "from_mode": prev_mode,
                    "to_mode": desired_mode,
                    "policy": self._policy,
                    "internet_reachable": self._internet_reachable,
                    "timestamp": self._last_checked_at,
                }
                self._transition_history.append(event)
                logger.info(
                    "Operating mode switched: %s -> %s (policy=%s, internet=%s)",
                    prev_mode,
                    desired_mode,
                    self._policy,
                    self._internet_reachable,
                )
                notify_args = (prev_mode, desired_mode)
            listeners = list(self._listeners)

        if notify_args:
            for cb in listeners:
                try:
                    cb(*notify_args)
                except Exception as exc:
                    logger.warning("Connectivity listener error ignored: %s", exc)

        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "policy": self._policy,
                "effective_mode": self._effective_mode,
                "internet_reachable": self._internet_reachable,
                "manual_online_degraded": (self._policy == "manual_online" and not self._internet_reachable),
                "last_checked_at": self._last_checked_at,
                "transitions": list(self._transition_history[-20:]),
            }
