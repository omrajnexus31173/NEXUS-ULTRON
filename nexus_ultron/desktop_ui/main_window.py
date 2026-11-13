"""Main PySide6 Desktop Window Shell for NEXUS ULTRON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..runtime import NexusUltronRuntime
from .screens import (
    AgentCenterScreen,
    AIConversationScreen,
    BrowserCenterScreen,
    DeveloperCenterScreen,
    FileIntelligenceScreen,
    HomeDashboardScreen,
    MemoryCenterScreen,
    AIModelCenterScreen,
    PluginManagerScreen,
    SecurityCenterScreen,
    SettingsScreen,
    SystemMonitorScreen,
    TaskCenterScreen,
    VoiceAssistantScreen,
)
from .theme import NEXUS_ULTRON_QSS

SCREEN_SPECS: list[tuple[str, str]] = [
    ("home_dashboard", "1. Home Dashboard"),
    ("ai_conversation", "2. AI Conversation"),
    ("voice_assistant", "3. Voice Assistant"),
    ("task_center", "4. Task Center"),
    ("agent_center", "5. Agent Center"),
    ("browser_center", "6. Browser Center"),
    ("ai_model_center", "7. AI Model Center"),
    ("memory_center", "8. Memory Center"),
    ("file_intelligence", "9. File Intelligence"),
    ("developer_center", "10. Developer Center"),
    ("system_monitor", "11. System Monitor"),
    ("security_center", "12. Security Center"),
    ("plugin_manager", "13. Plugin Manager"),
    ("settings", "14. Settings"),
]


class NexusUltronMainWindow(QMainWindow):
    """Premium Dark Futuristic PySide6 Desktop Application Shell with all 14 functional screens."""

    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        self.setWindowTitle("NEXUS ULTRON — ONE MIND. INFINITE CAPABILITIES.")
        self.resize(1380, 860)
        self.setStyleSheet(NEXUS_ULTRON_QSS)

        icon_path = self.runtime.repo_root / "assets" / "branding" / "logo_app_icon_square.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left Navigation Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(276)
        sb_lay = QVBoxLayout(sidebar)
        sb_lay.setContentsMargins(12, 14, 12, 14)
        sb_lay.setSpacing(4)

        brand_row = QHBoxLayout()
        emblem_path = self.runtime.repo_root / "assets" / "branding" / "logo_transparent_emblem.png"
        if emblem_path.exists():
            emblem_lbl = QLabel()
            pix = QPixmap(str(emblem_path)).scaled(36, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            emblem_lbl.setPixmap(pix)
            brand_row.addWidget(emblem_lbl)

        title_col = QVBoxLayout()
        t_lbl = QLabel("NEXUS ULTRON")
        t_lbl.setObjectName("BrandTitle")
        tag_lbl = QLabel("ONE MIND. INFINITE CAPABILITIES.")
        tag_lbl.setObjectName("BrandTagline")
        title_col.addWidget(t_lbl)
        title_col.addWidget(tag_lbl)
        brand_row.addLayout(title_col, 1)
        sb_lay.addLayout(brand_row)
        sb_lay.addSpacing(10)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in SCREEN_SPECS:
            btn = QPushButton(label)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _checked=False, k=key: self.navigate_to(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[key] = btn
            sb_lay.addWidget(btn)
        sb_lay.addStretch(1)

        tier_footer = QLabel(f"Profile: {self.runtime.hardware.tier_label}")
        tier_footer.setObjectName("MutedLabel")
        tier_footer.setWordWrap(True)
        sb_lay.addWidget(tier_footer)
        outer.addWidget(sidebar)

        # Right Main Content Area (Top Header + Stacked Screens)
        right_box = QWidget()
        right_lay = QVBoxLayout(right_box)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBarFrame")
        topbar.setFixedHeight(56)
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(18, 8, 18, 8)

        self.mode_badge = QLabel()
        self.mode_badge.setObjectName("MutedLabel")
        self.shield_badge = QLabel("PAYMENT ISOLATION: ACTIVE")
        self.shield_badge.setStyleSheet("color: #00E599; font-weight: 700;")

        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setObjectName("EmergencyButton")
        self.emergency_btn.clicked.connect(self._toggle_emergency_stop)

        tb_lay.addWidget(self.mode_badge)
        tb_lay.addStretch(1)
        tb_lay.addWidget(self.shield_badge)
        tb_lay.addSpacing(14)
        tb_lay.addWidget(self.emergency_btn)
        right_lay.addWidget(topbar)

        self.stack = QStackedWidget()
        self.screens: dict[str, Any] = {
            "home_dashboard": HomeDashboardScreen(self.runtime, self.navigate_to),
            "ai_conversation": AIConversationScreen(self.runtime),
            "voice_assistant": VoiceAssistantScreen(self.runtime),
            "task_center": TaskCenterScreen(self.runtime),
            "agent_center": AgentCenterScreen(self.runtime),
            "browser_center": BrowserCenterScreen(self.runtime),
            "ai_model_center": AIModelCenterScreen(self.runtime),
            "memory_center": MemoryCenterScreen(self.runtime),
            "file_intelligence": FileIntelligenceScreen(self.runtime),
            "developer_center": DeveloperCenterScreen(self.runtime),
            "system_monitor": SystemMonitorScreen(self.runtime),
            "security_center": SecurityCenterScreen(self.runtime),
            "plugin_manager": PluginManagerScreen(self.runtime),
            "settings": SettingsScreen(self.runtime),
        }
        for key, _ in SCREEN_SPECS:
            self.stack.addWidget(self.screens[key])

        right_lay.addWidget(self.stack, 1)
        outer.addWidget(right_box, 1)

        self.navigate_to("home_dashboard")
        self._update_header_badges()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._update_header_badges)
        self._poll_timer.start(3000)

    def navigate_to(self, screen_key: str) -> None:
        if screen_key not in self.screens:
            raise KeyError(f"Unknown screen '{screen_key}'")
        widget = self.screens[screen_key]
        self.stack.setCurrentWidget(widget)
        if screen_key in self.nav_buttons:
            self.nav_buttons[screen_key].setChecked(True)
        if hasattr(widget, "refresh_data"):
            widget.refresh_data()
        self._update_header_badges()

    def _toggle_emergency_stop(self) -> None:
        if self.runtime.permissions.emergency_stop_active:
            self.runtime.permissions.reset_emergency_stop()
        else:
            self.runtime.permissions.trigger_emergency_stop("User clicked Top-Bar Emergency Stop")
        self._update_header_badges()
        cur = self.stack.currentWidget()
        if hasattr(cur, "refresh_data"):
            cur.refresh_data()

    def _update_header_badges(self) -> None:
        conn = self.runtime.connectivity.status()
        estop = self.runtime.permissions.emergency_stop_active
        self.mode_badge.setText(
            f"MODE: {conn['effective_mode'].upper()} ({conn['policy']})  |  "
            f"STATUS: {'HALTED (EMERGENCY STOP)' if estop else 'AUTONOMOUS READY'}"
        )
        self.emergency_btn.setText("RESUME ULTRON" if estop else "EMERGENCY STOP")
        if self.runtime.payment_shield.is_locked_down:
            self.shield_badge.setText("PAYMENT LOCKDOWN ENGAGED (USER IN CONTROL)")
            self.shield_badge.setStyleSheet("color: #FFB020; font-weight: 800;")
        else:
            self.shield_badge.setText("PAYMENT ISOLATION SHIELD: ARMED")
            self.shield_badge.setStyleSheet("color: #00E599; font-weight: 700;")

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._poll_timer.stop()
        self.runtime.shutdown()
        super().closeEvent(event)
