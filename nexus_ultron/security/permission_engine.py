"""Persistent Permission Profiles, Emergency Stop Kill-Switch, and Shell Command Validator."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage.database import DatabaseManager
from .audit_logger import AuditLogger

PERMISSION_CATEGORIES = (
    "browser_access",
    "local_file_access",
    "application_launching",
    "project_workspace_access",
    "development_tools",
    "authorized_email_reading",
    "otp_retrieval",
    "approved_software_installation",
    "routine_automation",
)

IMMUTABLE_PROHIBITIONS = frozenset(
    {
        "payment_and_financial_transactions",
        "unauthorized_account_access",
        "credential_theft",
        "security_control_disabling",
        "destructive_operations_outside_scope",
        "uncontrolled_private_data_disclosure",
        "untrusted_software_execution",
    }
)

# Dangerous or prohibited shell command patterns
_BLOCKED_SHELL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)\brm\s+-[a-z]*r[a-z]*f[a-z]*\s+(/|\*|~|c:\\)"), "destructive root deletion"),
    (re.compile(r"(?i)\b(del|erase|rd|rmdir)\s+/[sqf]+\s+[a-z]:\\(windows|users|program\s*files|\*|$)"), "destructive Windows system deletion"),
    (re.compile(r"(?i)\bformat\s+[a-z]:"), "disk formatting prohibited"),
    (re.compile(r"(?i)\b(set-mppreference|disable-windowsoptionalfeature|sc\s+stop\s+windefend|netsh\s+advfirewall\s+set\s+allprofiles\s+state\s+off)"), "disabling OS security controls prohibited"),
    (re.compile(r"(?i)(?=.*google[\\/]+chrome[\\/]+user\s+data[\\/]+default)(?=.*(login\s+data|cookies|web\s+data))"), "accessing user Default Chrome credentials/cookies prohibited"),
    (re.compile(r"(?i)\b(mimikatz|sekurlsa|lsass|procdump.*lsass|reg\s+save\s+hklm\\sam)"), "credential theft/dumping prohibited"),
    (re.compile(r"(?i)(curl|wget|iwr|invoke-webrequest)\s+[^|]+\|\s*(sh|bash|powershell|pwsh|cmd)"), "piping untrusted remote scripts into shell prohibited"),
    (re.compile(r"(?i)\bpowershell(\.exe)?\s+.*-e(nc|ncodedcommand)\b"), "obfuscated encoded PowerShell execution prohibited"),
]


class PermissionDeniedError(PermissionError):
    """Raised when an action violates user permission profile, immutable security boundaries, or Emergency Stop."""


class PermissionEngine:
    """
    Enforces persistent autonomy permission profiles without nagging on routine authorized operations,
    while strictly blocking prohibited actions and supporting instant revocation + Emergency Stop.
    """

    def __init__(
        self,
        db: DatabaseManager,
        audit: AuditLogger,
        profiles_path: Path,
        default_profile: str = "autonomous_operator",
    ) -> None:
        self.db = db
        self.audit = audit
        self.profiles_path = Path(profiles_path)
        self._profiles = self._load_profiles()
        self._lock = threading.Lock()
        self._emergency_stop_active: bool = False
        self._emergency_callbacks: list[Any] = []
        self._ensure_initialized(default_profile)

    def _load_profiles(self) -> dict[str, Any]:
        if self.profiles_path.exists():
            data = json.loads(self.profiles_path.read_text(encoding="utf-8"))
            return data.get("profiles", {})
        return {}

    def _ensure_initialized(self, default_profile: str) -> None:
        existing = self.db.query_all("SELECT category FROM permission_grants")
        if not existing:
            self.apply_profile(default_profile, actor="installer_default")

    def register_emergency_stop_callback(self, callback: Any) -> None:
        with self._lock:
            self._emergency_callbacks.append(callback)

    @property
    def emergency_stop_active(self) -> bool:
        with self._lock:
            return self._emergency_stop_active

    def trigger_emergency_stop(self, reason: str = "User pressed Emergency Stop") -> dict[str, Any]:
        """Immediately halt all autonomous execution and block new actions until explicitly reset."""
        with self._lock:
            self._emergency_stop_active = True
            callbacks = list(self._emergency_callbacks)

        for cb in callbacks:
            try:
                cb()
            except Exception:
                pass

        event = self.audit.log_event(
            event_type="emergency_stop_activated",
            actor="user",
            category="emergency_stop",
            decision="halted_all",
            details=reason,
        )
        return {"emergency_stop_active": True, "audit_event": event}

    def reset_emergency_stop(self) -> dict[str, Any]:
        with self._lock:
            self._emergency_stop_active = False
        event = self.audit.log_event(
            event_type="emergency_stop_cleared",
            actor="user",
            category="emergency_stop",
            decision="resumed",
            details="Emergency Stop cleared by user.",
        )
        return {"emergency_stop_active": False, "audit_event": event}

    def apply_profile(self, profile_name: str, actor: str = "user") -> dict[str, bool]:
        if profile_name not in self._profiles:
            raise ValueError(f"Unknown permission profile '{profile_name}'")
        grants = self._profiles[profile_name].get("grants", {})
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connection() as conn:
            for category in PERMISSION_CATEGORIES:
                allowed = 1 if grants.get(category, False) else 0
                conn.execute(
                    """
                    INSERT INTO permission_grants (category, granted, profile_source, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(category) DO UPDATE SET
                        granted=excluded.granted,
                        profile_source=excluded.profile_source,
                        updated_at=excluded.updated_at
                    """,
                    (category, allowed, profile_name, now),
                )
        self.audit.log_event(
            event_type="permission_profile_applied",
            actor=actor,
            category="permissions",
            decision="updated",
            details=f"Applied permission profile '{profile_name}'",
        )
        return self.get_grants()

    def set_permission(self, category: str, granted: bool, actor: str = "user") -> None:
        if category in IMMUTABLE_PROHIBITIONS:
            self.audit.log_event(
                event_type="prohibited_permission_attempt",
                actor=actor,
                category=category,
                decision="blocked",
                details=f"Attempted to enable immutable prohibition '{category}'",
            )
            raise PermissionDeniedError(f"Category '{category}' is permanently prohibited by NEXUS ULTRON security architecture.")
        if category not in PERMISSION_CATEGORIES:
            raise ValueError(f"Unknown permission category '{category}'")
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO permission_grants (category, granted, profile_source, updated_at)
            VALUES (?, ?, 'custom', ?)
            ON CONFLICT(category) DO UPDATE SET granted=excluded.granted, profile_source='custom', updated_at=excluded.updated_at
            """,
            (category, 1 if granted else 0, now),
        )
        self.audit.log_event(
            event_type="permission_changed",
            actor=actor,
            category=category,
            decision="granted" if granted else "revoked",
            details=f"Permission '{category}' set to {granted}",
        )

    def revoke_all_permissions(self, actor: str = "user") -> dict[str, bool]:
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connection() as conn:
            for category in PERMISSION_CATEGORIES:
                conn.execute(
                    """
                    INSERT INTO permission_grants (category, granted, profile_source, updated_at)
                    VALUES (?, 0, 'revoked', ?)
                    ON CONFLICT(category) DO UPDATE SET granted=0, profile_source='revoked', updated_at=excluded.updated_at
                    """,
                    (category, now),
                )
        self.audit.log_event(
            event_type="permissions_revoked_all",
            actor=actor,
            category="permissions",
            decision="revoked_all",
            details="User immediately revoked all autonomy permissions.",
        )
        return self.get_grants()

    def get_grants(self) -> dict[str, bool]:
        rows = self.db.query_all("SELECT category, granted FROM permission_grants")
        mapping = {r["category"]: bool(r["granted"]) for r in rows}
        for cat in PERMISSION_CATEGORIES:
            mapping.setdefault(cat, False)
        return mapping

    def list_profiles(self) -> dict[str, Any]:
        return dict(self._profiles)

    def check_permission(self, category: str, actor: str = "agent", action_desc: str = "") -> bool:
        if self.emergency_stop_active:
            return False
        if category in IMMUTABLE_PROHIBITIONS:
            return False
        grants = self.get_grants()
        return bool(grants.get(category, False))

    def require_permission(self, category: str, actor: str = "agent", action_desc: str = "") -> None:
        if self.emergency_stop_active:
            self.audit.log_event(
                event_type="action_blocked_emergency_stop",
                actor=actor,
                category=category,
                decision="blocked",
                details=f"Blocked '{action_desc}' while Emergency Stop is active",
            )
            raise PermissionDeniedError("EMERGENCY STOP IS ACTIVE. All autonomous actions are halted.")

        if category in IMMUTABLE_PROHIBITIONS:
            self.audit.log_event(
                event_type="immutable_prohibition_enforced",
                actor=actor,
                category=category,
                decision="blocked",
                details=f"Blocked permanently prohibited action: {action_desc}",
            )
            raise PermissionDeniedError(f"Action permanently prohibited by security boundary: {category}")

        if not self.check_permission(category, actor=actor, action_desc=action_desc):
            self.audit.log_event(
                event_type="permission_denied",
                actor=actor,
                category=category,
                decision="denied",
                details=f"Permission '{category}' not granted for action: {action_desc}",
            )
            raise PermissionDeniedError(
                f"Permission '{category}' is currently disabled. Enable it in Security Center -> Permission Profiles."
            )

        self.audit.log_event(
            event_type="permission_authorized",
            actor=actor,
            category=category,
            decision="allowed",
            details=action_desc or f"Authorized routine operation in '{category}'",
        )

    def validate_shell_command(self, command: str, workspace_root: Path | None = None, actor: str = "coding_agent") -> None:
        """Validate AI/agent shell commands against user policy and destructive-action blocklist."""
        self.require_permission("development_tools", actor=actor, action_desc=f"shell: {command[:80]}")

        cleaned = (command or "").strip()
        if not cleaned:
            raise PermissionDeniedError("Empty shell command rejected.")

        for pattern, reason in _BLOCKED_SHELL_PATTERNS:
            if pattern.search(cleaned):
                self.audit.log_event(
                    event_type="dangerous_command_blocked",
                    actor=actor,
                    category="shell_sandbox",
                    decision="blocked",
                    details=f"Blocked shell command ({reason}): {cleaned[:120]}",
                )
                raise PermissionDeniedError(f"Blocked unsafe shell command ({reason}).")

        if workspace_root is not None and ".." in cleaned and ("rm " in cleaned or "del " in cleaned):
            self.audit.log_event(
                event_type="workspace_escape_blocked",
                actor=actor,
                category="shell_sandbox",
                decision="blocked",
                details=f"Blocked parent-directory destructive traversal: {cleaned[:120]}",
            )
            raise PermissionDeniedError("Destructive shell traversal outside project workspace is blocked.")
