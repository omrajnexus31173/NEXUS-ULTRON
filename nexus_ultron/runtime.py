"""Central Unified NEXUS ULTRON Runtime (Fast Startup, Lazy Model Loading & Clean Shutdown)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .agents.orchestrator import AgentOrchestrator
from .automation.browser_engine import BrowserIntelligenceEngine
from .automation.desktop_operator import DesktopOperator
from .automation.gmail_auth import GmailAuthEngine
from .core.config_manager import ConfigManager
from .core.connectivity import ConnectivityManager
from .core.hardware import detect_hardware_profile
from .core.logging_engine import LoggingEngine
from .core.resource_manager import ResourceManager
from .developer.dev_engine import AutonomousDevEngine
from .intelligence.file_intelligence import FileIntelligenceEngine
from .intelligence.planner import MasterPlanner
from .intelligence.providers import AIProviderRouter
from .plugins.plugin_manager import PluginManager
from .security.audit_logger import AuditLogger
from .security.credential_vault import CredentialVault
from .security.payment_isolation import PaymentIsolationEngine
from .security.permission_engine import PermissionEngine
from .security.prompt_guard import PromptInjectionShield
from .storage.database import DatabaseManager
from .storage.memory_system import MemorySystem
from .version import __app_name__, __motto__, __tagline__, __version__
from .voice.voice_engine import VoiceEngine


class NexusUltronRuntime:
    """
    Top-level application kernel wiring all 16 subsystems together.
    Designed for 8 GB RAM baseline laptops:
      - Startup completes in < 150 ms
      - Zero heavy LLMs preloaded at startup
      - Clean shutdown & persistent SQLite WAL state
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        data_root: Path | None = None,
        simulated_ram_gb: float | None = None,
        connectivity_probe_fn: Any | None = None,
    ) -> None:
        self.repo_root = Path(repo_root or Path(__file__).resolve().parent.parent).resolve()
        self.data_root = Path(data_root or (self.repo_root / "user_data")).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)

        # 1. Logging & Crash Diagnostics (with automatic secret/OTP redaction)
        self.logging_engine = LoggingEngine(self.data_root / "logs")
        self.logger = self.logging_engine.get_logger("runtime")

        # 2. Configuration Manager (with corrupted-config recovery)
        self.config = ConfigManager(
            default_config_path=self.repo_root / "config" / "default_config.json",
            user_config_path=self.data_root / "config.json",
        )

        # 3. Hardware Profiler & Intelligent Resource Manager
        self.hardware = detect_hardware_profile(
            storage_path=self.data_root,
            simulated_ram_gb=simulated_ram_gb,
            override_tier=self.config.get("hardware_override_tier"),
        )
        self.resources = ResourceManager(
            hardware=self.hardware,
            temp_dir=self.data_root / "temp",
        )

        # 4. SQLite WAL Database & Memory/Knowledge System
        self.db = DatabaseManager(
            db_path=self.data_root / "nexus_ultron.db",
            migrations_dir=self.repo_root / "migrations",
            max_db_size_mb=int(self.config.get("max_db_size_mb", 512)),
        )
        self.memory = MemorySystem(self.db)

        # 5. Security Architecture: Audit Log, Credential Vault, Permissions, Payment Shield & Prompt Shield
        self.audit = AuditLogger(self.db)
        self.vault = CredentialVault(self.data_root / "vault", audit=self.audit)
        self.permissions = PermissionEngine(
            db=self.db,
            audit=self.audit,
            profiles_path=self.repo_root / "config" / "permission_profiles.json",
            default_profile=str(self.config.get("security.active_permission_profile", "autonomous_operator")),
        )
        self.payment_shield = PaymentIsolationEngine(
            db=self.db,
            audit=self.audit,
            fail_closed_on_uncertainty=bool(self.config.get("security.fail_closed_on_uncertain_payment", True)),
        )
        self.prompt_shield = PromptInjectionShield(audit=self.audit)

        # 6. Hybrid Offline/Online Connectivity Controller
        self.connectivity = ConnectivityManager(
            initial_policy=str(self.config.get("mode_policy", "automatic")),
            flap_threshold=int(self.config.get("connectivity_flap_threshold", 2)),
            probe_fn=connectivity_probe_fn,
        )

        # 7. Intelligence Core, File Intelligence & Master Planner
        self.file_intel = FileIntelligenceEngine(self.permissions, self.prompt_shield)
        self.ai_router = AIProviderRouter(
            connectivity=self.connectivity,
            resources=self.resources,
            vault=self.vault,
            memory=self.memory,
            payment_shield=self.payment_shield,
            prompt_shield=self.prompt_shield,
            provider_config=self.config.get("ai_providers", {}),
        )
        self.planner = MasterPlanner(self.db, self.payment_shield, self.audit)

        # 8. Browser Intelligence, Desktop Operator & Authorized Gmail/OTP Engine
        self.browser = BrowserIntelligenceEngine(
            db=self.db,
            data_root=self.data_root,
            permissions=self.permissions,
            payment_shield=self.payment_shield,
            prompt_shield=self.prompt_shield,
        )
        self.desktop = DesktopOperator(
            db=self.db,
            permissions=self.permissions,
            payment_shield=self.payment_shield,
        )
        self.gmail = GmailAuthEngine(
            vault=self.vault,
            permissions=self.permissions,
            payment_shield=self.payment_shield,
            prompt_shield=self.prompt_shield,
            audit=self.audit,
            otp_max_age_seconds=int(self.config.get("gmail_auth.otp_max_age_seconds", 300)),
        )

        # 9. Autonomous Software Development Engine
        self.dev_engine = AutonomousDevEngine(
            workspaces_root=self.data_root / "workspaces",
            db=self.db,
            permissions=self.permissions,
            ai_router=self.ai_router,
            audit=self.audit,
        )

        # 10. Shared Service Registry for Multi-Agent Orchestrator & Plugin System
        self.services: dict[str, Any] = {
            "data_root": self.data_root,
            "resources": self.resources,
            "memory": self.memory,
            "file_intel": self.file_intel,
            "ai_router": self.ai_router,
            "browser": self.browser,
            "desktop": self.desktop,
            "gmail": self.gmail,
            "dev_engine": self.dev_engine,
            "audit": self.audit,
            "payment_shield": self.payment_shield,
        }
        self.orchestrator = AgentOrchestrator(
            planner=self.planner,
            resources=self.resources,
            permissions=self.permissions,
            services=self.services,
        )
        self.plugins = PluginManager(
            db=self.db,
            permissions=self.permissions,
            audit=self.audit,
            user_plugins_dir=self.data_root / "plugins",
            services=self.services,
        )
        self.voice = VoiceEngine(
            config=self.config,
            ai_router=self.ai_router,
            audio_cache_dir=self.data_root / "temp" / "voice",
        )

        # Recover any interrupted workflows from prior session into resumable Pending state
        self.resumable_tasks = self.planner.get_resumable_tasks_after_restart()
        self.logger.info(
            "%s v%s initialized in %s (%s)",
            __app_name__,
            __version__,
            self.hardware.tier_label,
            self.connectivity.effective_mode.upper(),
        )

    def dashboard_overview(self) -> dict[str, Any]:
        """Aggregate live state for Home Dashboard (PySide6 Desktop & Web Command Center)."""
        telemetry = self.resources.snapshot()
        conn = self.connectivity.status()
        orch = self.orchestrator.active_summary()
        tasks = self.planner.list_tasks(limit=12)
        active_task = next((t for t in tasks if t["state"] == "Running"), tasks[0] if tasks else None)
        return {
            "app_name": __app_name__,
            "tagline": __tagline__,
            "motto": __motto__,
            "version": __version__,
            "availability": "EMERGENCY_STOP" if self.permissions.emergency_stop_active else "OPERATIONAL",
            "emergency_stop_active": self.permissions.emergency_stop_active,
            "payment_isolation_locked": self.payment_shield.is_locked_down,
            "connectivity": conn,
            "hardware": self.hardware.to_dict(),
            "telemetry": telemetry,
            "active_task": active_task,
            "orchestrator": orch,
            "recent_tasks": tasks[:8],
            "recent_logs": self.logging_engine.recent_logs(limit=25),
        }

    def shutdown(self) -> None:
        """Safe application shutdown cleaning temp files and stopping workers."""
        try:
            self.voice.interrupt_speech()
            self.orchestrator.shutdown()
            self.resources.cleanup_temp_files(
                max_age_hours=float(self.config.get("temp_cleanup_age_hours", 24))
            )
            self.db.enforce_growth_limits()
            self.logger.info("NEXUS ULTRON shutdown completed cleanly.")
        except Exception as exc:
            self.logging_engine.record_crash_report("shutdown", exc)
