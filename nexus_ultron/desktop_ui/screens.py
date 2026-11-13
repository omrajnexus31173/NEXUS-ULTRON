"""All 14 Required Functional PySide6 Screens Wired Directly to NexusUltronRuntime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..agents.base_agent import BaseAgent, SharedTaskContext
from ..intelligence.file_intelligence import safe_calculate
from ..runtime import NexusUltronRuntime
from ..security.payment_isolation import PaymentIsolationTriggered


def _make_card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("CardFrame")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)
    if title:
        lbl = QLabel(title)
        lbl.setObjectName("MutedLabel")
        layout.addWidget(lbl)
    return frame, layout


def _make_heading(title: str, subtitle: str) -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 6)
    lay.setSpacing(2)
    h = QLabel(title)
    h.setObjectName("ScreenHeading")
    s = QLabel(subtitle)
    s.setObjectName("MutedLabel")
    lay.addWidget(h)
    lay.addWidget(s)
    return box


# ---------------------------------------------------------------------------
# 1. HOME DASHBOARD
# ---------------------------------------------------------------------------
class HomeDashboardScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime, navigate_cb: Callable[[str], None]) -> None:
        super().__init__()
        self.runtime = runtime
        self.navigate_cb = navigate_cb
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        root.addWidget(_make_heading("HOME COMMAND DASHBOARD", "Autonomous System Availability, Live Telemetry & Quick Operations"))

        grid = QGridLayout()
        grid.setSpacing(10)
        self.metric_labels: dict[str, QLabel] = {}
        cards_spec = [
            ("availability", "ULTRON Availability"),
            ("mode", "Operating Mode"),
            ("active_task", "Active Task"),
            ("agents", "Registered / Busy Agents"),
            ("cpu", "CPU Usage"),
            ("ram", "RAM Usage"),
            ("storage", "Available Storage"),
            ("battery", "Battery & Power"),
        ]
        for idx, (key, label) in enumerate(cards_spec):
            card, clay = _make_card(label)
            val = QLabel("--")
            val.setObjectName("MetricValue")
            val.setWordWrap(True)
            clay.addWidget(val)
            self.metric_labels[key] = val
            grid.addWidget(card, idx // 4, idx % 4)
        root.addLayout(grid)

        # Quick Actions Bar (every button executes a real action)
        qa_card, qa_lay = _make_card("Quick Actions")
        btn_row = QHBoxLayout()
        for label, target in [
            ("New AI Conversation", "ai_conversation"),
            ("Launch Autonomous Task", "task_center"),
            ("Build Software App", "developer_center"),
            ("Open NEXUS Browser", "browser_center"),
            ("Verify Security Posture", "security_center"),
        ]:
            b = QPushButton(label)
            b.setObjectName("PrimaryButton" if target == "task_center" else "")
            b.clicked.connect(lambda _checked=False, t=target: self.navigate_cb(t))
            btn_row.addWidget(b)
        refresh_btn = QPushButton("Refresh Telemetry")
        refresh_btn.clicked.connect(self.refresh_data)
        btn_row.addWidget(refresh_btn)
        qa_lay.addLayout(btn_row)
        root.addWidget(qa_card)

        # Recent Activity Log
        act_card, act_lay = _make_card("Recent Autonomous Activity & Redacted Diagnostic Stream")
        self.activity_box = QPlainTextEdit()
        self.activity_box.setReadOnly(True)
        act_lay.addWidget(self.activity_box)
        root.addWidget(act_card, 1)
        self.refresh_data()

    def refresh_data(self) -> None:
        ov = self.runtime.dashboard_overview()
        tel = ov["telemetry"]
        conn = ov["connectivity"]
        orch = ov["orchestrator"]
        act_task = ov["active_task"]
        self.metric_labels["availability"].setText(ov["availability"])
        self.metric_labels["mode"].setText(f"{conn['effective_mode'].upper()} ({conn['policy']})")
        self.metric_labels["active_task"].setText(
            f"{act_task['state']}: {act_task['objective'][:26]}..." if act_task else "Standby (0 Running)"
        )
        self.metric_labels["agents"].setText(
            f"{orch['registered_agent_count']} Ready | {len(orch['running_tasks'])} Active | {orch['queued_count']} Queued"
        )
        self.metric_labels["cpu"].setText(f"{tel['cpu_percent']}%")
        self.metric_labels["ram"].setText(f"{tel['ram_percent']}% ({tel['ram_available_gb']} GB Free)")
        self.metric_labels["storage"].setText(f"{tel['storage_free_gb']} GB Free")
        self.metric_labels["battery"].setText(tel["battery"]["status_label"])

        lines = [f"[{item['timestamp'][:19]}] [{item['level']}] {item['message']}" for item in ov["recent_logs"]]
        self.activity_box.setPlainText("\n".join(lines) or "NEXUS ULTRON initialized cleanly.")


# ---------------------------------------------------------------------------
# 2. AI CONVERSATION
# ---------------------------------------------------------------------------
class AIConversationScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        conv = self.runtime.memory.create_conversation("Primary Command Session", self.runtime.connectivity.effective_mode)
        self.current_conv_id = conv["id"]

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("AI CONVERSATION ENGINE", "Hybrid Local & Cloud Reasoning with Persistent SQLite History"))

        top_row = QHBoxLayout()
        self.provider_combo = QComboBox()
        for p in self.runtime.ai_router.list_providers():
            self.provider_combo.addItem(f"{p['name']} [{p['mode']}]", p["id"])
        new_session_btn = QPushButton("New Conversation")
        new_session_btn.clicked.connect(self._new_session)
        top_row.addWidget(QLabel("Active Provider:"))
        top_row.addWidget(self.provider_combo, 1)
        top_row.addWidget(new_session_btn)
        root.addLayout(top_row)

        self.transcript_view = QPlainTextEdit()
        self.transcript_view.setReadOnly(True)
        root.addWidget(self.transcript_view, 1)

        input_row = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Ask ULTRON anything, calculate math, recall memory, or plan an engineering task...")
        self.prompt_input.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("Send Directive")
        self.send_btn.setObjectName("PrimaryButton")
        self.send_btn.clicked.connect(self.send_message)
        input_row.addWidget(self.prompt_input, 1)
        input_row.addWidget(self.send_btn)
        root.addLayout(input_row)

    def _new_session(self) -> None:
        conv = self.runtime.memory.create_conversation("Session", self.runtime.connectivity.effective_mode)
        self.current_conv_id = conv["id"]
        self.transcript_view.clear()

    def send_message(self) -> None:
        text = self.prompt_input.text().strip()
        if not text:
            return
        self.prompt_input.clear()
        prov = self.provider_combo.currentData()
        res = self.runtime.ai_router.generate_response(text, conversation_id=self.current_conv_id, preferred_provider=prov)
        self.refresh_data()
        _ = res

    def refresh_data(self) -> None:
        msgs = self.runtime.memory.get_conversation_messages(self.current_conv_id)
        rendered = [
            f"{'YOU' if m['role'] == 'user' else 'ULTRON [' + m['provider'] + ']'}: {m['content']}"
            for m in msgs
        ]
        self.transcript_view.setPlainText("\n\n".join(rendered))


# ---------------------------------------------------------------------------
# 3. VOICE ASSISTANT
# ---------------------------------------------------------------------------
class VoiceAssistantScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("VOICE ASSISTANT", "Wake-Word Detection, Push-to-Talk, VAD & Interruptible Offline Speech"))

        cfg_card, cfg_lay = _make_card("Voice Configuration")
        row1 = QHBoxLayout()
        self.wake_input = QLineEdit(self.runtime.voice.get_settings()["wake_word"])
        self.mic_combo = QComboBox()
        for mic in self.runtime.voice.list_microphones():
            self.mic_combo.addItem(mic["name"], mic["id"])
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(100, 280)
        self.rate_slider.setValue(self.runtime.voice.get_settings()["tts_rate"])
        save_btn = QPushButton("Apply Voice Config")
        save_btn.clicked.connect(self._save_voice_cfg)
        row1.addWidget(QLabel("Wake Phrase:"))
        row1.addWidget(self.wake_input)
        row1.addWidget(QLabel("Microphone:"))
        row1.addWidget(self.mic_combo)
        row1.addWidget(QLabel("Speech Rate:"))
        row1.addWidget(self.rate_slider)
        row1.addWidget(save_btn)
        cfg_lay.addLayout(row1)
        root.addWidget(cfg_card)

        ctrl_card, ctrl_lay = _make_card("Push-to-Talk, Interruptible Speech & Text Fallback")
        ctrl_row = QHBoxLayout()
        self.utterance_input = QLineEdit()
        self.utterance_input.setPlaceholderText("Say e.g. 'Hey Ultron, calculate 256 * 16'...")
        self.ptt_btn = QPushButton("Push-to-Talk Speak")
        self.ptt_btn.setObjectName("PrimaryButton")
        self.ptt_btn.clicked.connect(self._run_voice_turn)
        self.interrupt_btn = QPushButton("Interrupt ULTRON Speech")
        self.interrupt_btn.setObjectName("EmergencyButton")
        self.interrupt_btn.clicked.connect(self._interrupt)
        ctrl_row.addWidget(self.utterance_input, 1)
        ctrl_row.addWidget(self.ptt_btn)
        ctrl_row.addWidget(self.interrupt_btn)
        ctrl_lay.addLayout(ctrl_row)

        self.voice_status = QPlainTextEdit()
        self.voice_status.setReadOnly(True)
        ctrl_lay.addWidget(self.voice_status)
        root.addWidget(ctrl_card, 1)

    def _save_voice_cfg(self) -> None:
        updated = self.runtime.voice.update_settings(
            wake_word=self.wake_input.text(),
            tts_rate=self.rate_slider.value(),
            selected_microphone=self.mic_combo.currentData(),
        )
        self.voice_status.setPlainText(json.dumps(updated, indent=2))

    def _run_voice_turn(self) -> None:
        self.runtime.voice.start_push_to_talk()
        txt = self.utterance_input.text().strip() or "Hey Ultron, system status"
        out = self.runtime.voice.process_voice_turn(txt, require_wake_word=False)
        self.runtime.voice.stop_push_to_talk()
        self.voice_status.setPlainText(json.dumps(out, indent=2))

    def _interrupt(self) -> None:
        res = self.runtime.voice.interrupt_speech()
        self.voice_status.setPlainText(f"Speech Interrupted Immediately: {json.dumps(res)}")

    def refresh_data(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 4. TASK CENTER
# ---------------------------------------------------------------------------
class TaskCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("AUTONOMOUS TASK CENTER", "Master Planning Engine, Explicit Task States & Verified Execution"))

        form_row = QHBoxLayout()
        self.obj_input = QLineEdit()
        self.obj_input.setPlaceholderText("Enter objective (e.g. 'Build an inventory management application with auth and billing')...")
        self.prio_spin = QSpinBox()
        self.prio_spin.setRange(1, 10)
        self.prio_spin.setValue(7)
        self.exec_btn = QPushButton("Plan & Execute Objective")
        self.exec_btn.setObjectName("PrimaryButton")
        self.exec_btn.clicked.connect(self._execute_objective)
        self.cancel_btn = QPushButton("Cancel Selected")
        self.cancel_btn.clicked.connect(self._cancel_selected)
        form_row.addWidget(self.obj_input, 1)
        form_row.addWidget(QLabel("Priority:"))
        form_row.addWidget(self.prio_spin)
        form_row.addWidget(self.exec_btn)
        form_row.addWidget(self.cancel_btn)
        root.addLayout(form_row)

        self.task_table = QTableWidget(0, 6)
        self.task_table.setHorizontalHeaderLabels(["Task ID", "State", "Verified", "Category", "Priority", "Objective / Summary"])
        self.task_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        root.addWidget(self.task_table, 1)
        self.refresh_data()

    def _execute_objective(self) -> None:
        obj = self.obj_input.text().strip()
        if not obj:
            return
        self.obj_input.clear()
        try:
            self.runtime.orchestrator.run_objective_sync(
                objective=obj,
                priority=self.prio_spin.value(),
                mode_used=self.runtime.connectivity.effective_mode,
            )
        except PaymentIsolationTriggered:
            pass
        self.refresh_data()

    def _cancel_selected(self) -> None:
        row = self.task_table.currentRow()
        if row >= 0:
            tid_item = self.task_table.item(row, 0)
            if tid_item:
                self.runtime.planner.cancel_task(tid_item.text())
                self.refresh_data()

    def refresh_data(self) -> None:
        tasks = self.runtime.planner.list_tasks(limit=40)
        self.task_table.setRowCount(len(tasks))
        for idx, t in enumerate(tasks):
            self.task_table.setItem(idx, 0, QTableWidgetItem(t["id"]))
            self.task_table.setItem(idx, 1, QTableWidgetItem(t["state"]))
            self.task_table.setItem(idx, 2, QTableWidgetItem("YES" if t["verified"] else "NO"))
            self.task_table.setItem(idx, 3, QTableWidgetItem(t["category"]))
            self.task_table.setItem(idx, 4, QTableWidgetItem(str(t["priority"])))
            self.task_table.setItem(idx, 5, QTableWidgetItem(f"{t['objective']} — {t['result_summary']}"))


# ---------------------------------------------------------------------------
# 5. AGENT CENTER
# ---------------------------------------------------------------------------
class _CustomRegisteredAgent(BaseAgent):
    def __init__(self, agent_id: str, display_name: str, specialty: str) -> None:
        self.agent_id = agent_id
        self.display_name = display_name
        self.specialty = specialty

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        return {"custom_agent": self.agent_id, "status": "completed", "subtask": subtask["title"]}


class AgentCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("MULTI-AGENT ORCHESTRATION CENTER", "12 Built-in Specialized Agents + Dynamic Agent Registration"))

        reg_row = QHBoxLayout()
        self.id_in = QLineEdit()
        self.id_in.setPlaceholderText("custom_security_reviewer")
        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("Security Code Reviewer Agent")
        self.spec_in = QLineEdit()
        self.spec_in.setPlaceholderText("Static vulnerability & dependency auditing")
        reg_btn = QPushButton("Register Dynamic Agent")
        reg_btn.setObjectName("PrimaryButton")
        reg_btn.clicked.connect(self._register_custom)
        reg_row.addWidget(self.id_in)
        reg_row.addWidget(self.name_in)
        reg_row.addWidget(self.spec_in, 1)
        reg_row.addWidget(reg_btn)
        root.addLayout(reg_row)

        self.agent_table = QTableWidget(0, 4)
        self.agent_table.setHorizontalHeaderLabels(["Agent ID", "Display Name", "Status", "Specialty"])
        self.agent_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.agent_table, 1)
        self.refresh_data()

    def _register_custom(self) -> None:
        aid = self.id_in.text().strip()
        name = self.name_in.text().strip()
        spec = self.spec_in.text().strip() or "Custom autonomous specialist"
        if aid and name:
            self.runtime.orchestrator.register_agent(_CustomRegisteredAgent(aid, name, spec))
            self.id_in.clear()
            self.name_in.clear()
            self.spec_in.clear()
            self.refresh_data()

    def refresh_data(self) -> None:
        agents = self.runtime.orchestrator.list_agents()
        self.agent_table.setRowCount(len(agents))
        for idx, a in enumerate(agents):
            self.agent_table.setItem(idx, 0, QTableWidgetItem(a["agent_id"]))
            self.agent_table.setItem(idx, 1, QTableWidgetItem(a["display_name"]))
            self.agent_table.setItem(idx, 2, QTableWidgetItem(a["status"].upper()))
            self.agent_table.setItem(idx, 3, QTableWidgetItem(a["specialty"]))


# ---------------------------------------------------------------------------
# 6. BROWSER CENTER (Isolated Chrome + Dedicated NEXUS Browser)
# ---------------------------------------------------------------------------
class BrowserCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("BROWSER INTELLIGENCE CENTER", "Isolated ULTRON Chrome Profile & Dedicated NEXUS Browser with Payment Shield"))

        chrome_card, chrome_lay = _make_card("Environment A: Isolated ULTRON Chrome Controller (User Default Chrome Untouched)")
        crow = QHBoxLayout()
        iso = self.runtime.browser.get_chrome_isolation_status()
        self.chrome_lbl = QLabel(
            f"Isolated Profile: {iso['ultron_isolated_profile_dir']} | User Chrome Untouched: {iso['user_chrome_untouched']}"
        )
        launch_chrome_btn = QPushButton("Launch Isolated Chrome")
        launch_chrome_btn.clicked.connect(lambda: self._launch_chrome("https://www.google.com"))
        crow.addWidget(self.chrome_lbl, 1)
        crow.addWidget(launch_chrome_btn)
        chrome_lay.addLayout(crow)
        root.addWidget(chrome_card)

        nexus_card, nexus_lay = _make_card("Environment B: NEXUS Browser (Multi-Tab, Profiles, Bookmarks & Payment Shield)")
        nav_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["default", "research", "automation"])
        self.url_input = QLineEdit("https://docs.python.org/3/")
        go_btn = QPushButton("Navigate / Search")
        go_btn.setObjectName("PrimaryButton")
        go_btn.clicked.connect(self._navigate)
        new_tab_btn = QPushButton("+ New Tab")
        new_tab_btn.clicked.connect(self._new_tab)
        bm_btn = QPushButton("Bookmark")
        bm_btn.clicked.connect(self._bookmark)
        nav_row.addWidget(QLabel("Profile:"))
        nav_row.addWidget(self.profile_combo)
        nav_row.addWidget(self.url_input, 1)
        nav_row.addWidget(go_btn)
        nav_row.addWidget(new_tab_btn)
        nav_row.addWidget(bm_btn)
        nexus_lay.addLayout(nav_row)

        self.browser_view = QPlainTextEdit()
        self.browser_view.setReadOnly(True)
        nexus_lay.addWidget(self.browser_view, 1)
        root.addWidget(nexus_card, 1)
        self.refresh_data()

    def _launch_chrome(self, url: str) -> None:
        try:
            res = self.runtime.browser.launch_isolated_chrome(url)
            self.browser_view.setPlainText(json.dumps(res, indent=2))
        except Exception as exc:
            self.browser_view.setPlainText(f"Blocked: {exc}")

    def _navigate(self) -> None:
        tabs = self.runtime.browser.list_tabs()
        tid = tabs[-1]["tab_id"]
        try:
            res = self.runtime.browser.navigate_tab(tid, self.url_input.text())
            self.browser_view.setPlainText(json.dumps(res, indent=2))
        except PaymentIsolationTriggered as exc:
            self.browser_view.setPlainText(f"PAYMENT ISOLATION TRIGGERED:\n{exc}")

    def _new_tab(self) -> None:
        try:
            res = self.runtime.browser.open_tab(self.url_input.text(), profile=self.profile_combo.currentText())
            self.browser_view.setPlainText(json.dumps(res, indent=2))
        except PaymentIsolationTriggered as exc:
            self.browser_view.setPlainText(f"PAYMENT ISOLATION TRIGGERED:\n{exc}")

    def _bookmark(self) -> None:
        bm = self.runtime.browser.add_bookmark(self.url_input.text()[:40], self.url_input.text(), self.profile_combo.currentText())
        self.browser_view.setPlainText(f"Saved Bookmark:\n{json.dumps(bm, indent=2)}")

    def refresh_data(self) -> None:
        tabs = self.runtime.browser.list_tabs()
        self.browser_view.setPlainText(json.dumps({"open_tabs": tabs, "bookmarks": self.runtime.browser.list_bookmarks()}, indent=2))


# ---------------------------------------------------------------------------
# 7. AI MODEL CENTER
# ---------------------------------------------------------------------------
class AIModelCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("AI MODEL & CREDENTIAL VAULT CENTER", "On-Demand Local Inference & Encrypted Cloud API Configuration"))

        vault_card, v_lay = _make_card("Store API Key in Windows Credential Manager + AES Vault")
        vrow = QHBoxLayout()
        self.key_combo = QComboBox()
        self.key_combo.addItems(["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY"])
        self.secret_in = QLineEdit()
        self.secret_in.setEchoMode(QLineEdit.Password)
        self.secret_in.setPlaceholderText("Enter API key (never logged or stored in plain text)...")
        save_key_btn = QPushButton("Save to Secure Vault")
        save_key_btn.setObjectName("PrimaryButton")
        save_key_btn.clicked.connect(self._save_key)
        vrow.addWidget(self.key_combo)
        vrow.addWidget(self.secret_in, 1)
        vrow.addWidget(save_key_btn)
        v_lay.addLayout(vrow)
        root.addWidget(vault_card)

        self.model_table = QTableWidget(0, 5)
        self.model_table.setHorizontalHeaderLabels(["Provider ID", "Model / Engine", "Mode", "Configured", "RAM Profile"])
        self.model_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.model_table, 1)
        self.refresh_data()

    def _save_key(self) -> None:
        val = self.secret_in.text().strip()
        if val:
            self.runtime.vault.set_secret(self.key_combo.currentText(), val)
            self.secret_in.clear()
            self.refresh_data()

    def refresh_data(self) -> None:
        providers = self.runtime.ai_router.list_providers()
        self.model_table.setRowCount(len(providers))
        for i, p in enumerate(providers):
            self.model_table.setItem(i, 0, QTableWidgetItem(p["id"]))
            self.model_table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.model_table.setItem(i, 2, QTableWidgetItem(p["mode"]))
            self.model_table.setItem(i, 3, QTableWidgetItem("YES" if p["configured"] else "Optional"))
            self.model_table.setItem(i, 4, QTableWidgetItem(p["ram_requirement"]))


# ---------------------------------------------------------------------------
# 8. MEMORY CENTER
# ---------------------------------------------------------------------------
class MemoryCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("PERSISTENT MEMORY & KNOWLEDGE CENTER", "SQLite FTS5 + Local Semantic Search with Sensitive-Data Blocking"))

        add_row = QHBoxLayout()
        self.ns_combo = QComboBox()
        self.ns_combo.addItems(["long_term", "knowledge", "project", "instruction", "temporary"])
        self.title_in = QLineEdit()
        self.title_in.setPlaceholderText("Memory title...")
        self.content_in = QLineEdit()
        self.content_in.setPlaceholderText("Knowledge or preference content...")
        add_btn = QPushButton("Save Memory")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self._add_mem)
        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self._del_selected)
        add_row.addWidget(self.ns_combo)
        add_row.addWidget(self.title_in)
        add_row.addWidget(self.content_in, 1)
        add_row.addWidget(add_btn)
        add_row.addWidget(del_btn)
        root.addLayout(add_row)

        search_row = QHBoxLayout()
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("Hybrid FTS5 + Semantic search across local memory...")
        search_btn = QPushButton("Search Memory")
        search_btn.clicked.connect(self._search)
        search_row.addWidget(self.search_in, 1)
        search_row.addWidget(search_btn)
        root.addLayout(search_row)

        self.mem_table = QTableWidget(0, 4)
        self.mem_table.setHorizontalHeaderLabels(["ID", "Namespace", "Title", "Content"])
        self.mem_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        root.addWidget(self.mem_table, 1)
        self.refresh_data()

    def _add_mem(self) -> None:
        t = self.title_in.text().strip()
        c = self.content_in.text().strip()
        if t and c:
            try:
                self.runtime.memory.add_memory(t, c, namespace=self.ns_combo.currentText())
                self.title_in.clear()
                self.content_in.clear()
                self.refresh_data()
            except Exception:
                pass

    def _del_selected(self) -> None:
        row = self.mem_table.currentRow()
        if row >= 0 and self.mem_table.item(row, 0):
            self.runtime.memory.delete_memory(self.mem_table.item(row, 0).text())
            self.refresh_data()

    def _search(self) -> None:
        q = self.search_in.text().strip()
        items = self.runtime.memory.search_memory(q) if q else self.runtime.memory.list_memories()
        self._populate(items)

    def refresh_data(self) -> None:
        self._populate(self.runtime.memory.list_memories())

    def _populate(self, items: list[dict[str, Any]]) -> None:
        self.mem_table.setRowCount(len(items))
        for i, m in enumerate(items):
            self.mem_table.setItem(i, 0, QTableWidgetItem(m["id"]))
            self.mem_table.setItem(i, 1, QTableWidgetItem(m["namespace"]))
            self.mem_table.setItem(i, 2, QTableWidgetItem(m["title"]))
            self.mem_table.setItem(i, 3, QTableWidgetItem(m["content"]))


# ---------------------------------------------------------------------------
# 9. FILE INTELLIGENCE
# ---------------------------------------------------------------------------
class FileIntelligenceScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("FILE, DOCUMENT & SPREADSHEET INTELLIGENCE", "Offline Search, PDF/DOCX/XLSX Processing & Safe Calculator"))

        row1 = QHBoxLayout()
        self.dir_in = QLineEdit(str(self.runtime.repo_root))
        self.pat_in = QLineEdit("*.md")
        search_btn = QPushButton("Search Local Files")
        search_btn.setObjectName("PrimaryButton")
        search_btn.clicked.connect(self._search_files)
        row1.addWidget(QLabel("Directory:"))
        row1.addWidget(self.dir_in, 1)
        row1.addWidget(QLabel("Glob:"))
        row1.addWidget(self.pat_in)
        row1.addWidget(search_btn)
        root.addLayout(row1)

        calc_row = QHBoxLayout()
        self.calc_in = QLineEdit("sqrt(256) * 12 + mean([10, 20, 30])")
        calc_btn = QPushButton("Evaluate Expression")
        calc_btn.clicked.connect(self._run_calc)
        calc_row.addWidget(QLabel("Offline Calculator:"))
        calc_row.addWidget(self.calc_in, 1)
        calc_row.addWidget(calc_btn)
        root.addLayout(calc_row)

        self.out_box = QPlainTextEdit()
        self.out_box.setReadOnly(True)
        root.addWidget(self.out_box, 1)

    def _search_files(self) -> None:
        hits = self.runtime.file_intel.search_files(Path(self.dir_in.text()), pattern=self.pat_in.text())
        self.out_box.setPlainText(json.dumps(hits, indent=2))

    def _run_calc(self) -> None:
        try:
            val = safe_calculate(self.calc_in.text())
            self.out_box.setPlainText(f"Verified Result: {val}")
        except Exception as exc:
            self.out_box.setPlainText(f"Calculation Error: {exc}")

    def refresh_data(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 10. DEVELOPER CENTER
# ---------------------------------------------------------------------------
class DeveloperCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("AUTONOMOUS DEVELOPER CENTER", "End-to-End Scaffolding, Multi-Language Codegen, Self-Debugging, Testing & Packaging"))

        row = QHBoxLayout()
        self.spec_in = QLineEdit()
        self.spec_in.setPlaceholderText("Describe software to build (e.g. 'Complete inventory management app with auth, billing & dashboard')...")
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["python", "javascript", "c", "cpp"])
        build_btn = QPushButton("Build, Test & Package App")
        build_btn.setObjectName("PrimaryButton")
        build_btn.clicked.connect(self._build_app)
        row.addWidget(self.spec_in, 1)
        row.addWidget(self.lang_combo)
        row.addWidget(build_btn)
        root.addLayout(row)

        self.proj_table = QTableWidget(0, 5)
        self.proj_table.setHorizontalHeaderLabels(["Project Name", "Language", "Verified", "Framework", "Workspace Path"])
        self.proj_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.proj_table, 1)
        self.refresh_data()

    def _build_app(self) -> None:
        obj = self.spec_in.text().strip()
        if not obj:
            return
        self.runtime.dev_engine.build_application(obj, requested_language=self.lang_combo.currentText())
        self.spec_in.clear()
        self.refresh_data()

    def refresh_data(self) -> None:
        projs = self.runtime.dev_engine.list_projects()
        self.proj_table.setRowCount(len(projs))
        for i, p in enumerate(projs):
            self.proj_table.setItem(i, 0, QTableWidgetItem(p["name"]))
            self.proj_table.setItem(i, 1, QTableWidgetItem(p["language"]))
            self.proj_table.setItem(i, 2, QTableWidgetItem("VERIFIED" if p["verified"] else "FAILED"))
            self.proj_table.setItem(i, 3, QTableWidgetItem(p["framework"]))
            self.proj_table.setItem(i, 4, QTableWidgetItem(p["workspace_path"]))


# ---------------------------------------------------------------------------
# 11. SYSTEM MONITOR
# ---------------------------------------------------------------------------
class SystemMonitorScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("SYSTEM MONITOR & RESOURCE MANAGER", "Real-Time Hardware Telemetry, Adaptive Concurrency & Process Inspector"))

        bars_card, bars_lay = _make_card("Resource Utilization")
        self.cpu_bar = QProgressBar()
        self.ram_bar = QProgressBar()
        self.disk_bar = QProgressBar()
        bars_lay.addWidget(QLabel("CPU Load"))
        bars_lay.addWidget(self.cpu_bar)
        bars_lay.addWidget(QLabel("RAM Utilization"))
        bars_lay.addWidget(self.ram_bar)
        bars_lay.addWidget(QLabel("Disk Utilization"))
        bars_lay.addWidget(self.disk_bar)

        act_row = QHBoxLayout()
        ref_btn = QPushButton("Refresh Snapshot")
        ref_btn.clicked.connect(self.refresh_data)
        clean_btn = QPushButton("Clean Temporary Files")
        clean_btn.clicked.connect(lambda: self.runtime.resources.cleanup_temp_files(0.0) or self.refresh_data())
        act_row.addWidget(ref_btn)
        act_row.addWidget(clean_btn)
        act_row.addStretch()
        bars_lay.addLayout(act_row)
        root.addWidget(bars_card)

        self.proc_table = QTableWidget(0, 5)
        self.proc_table.setHorizontalHeaderLabels(["PID", "Process", "CPU %", "RAM (MB)", "Status"])
        self.proc_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        root.addWidget(self.proc_table, 1)
        self.refresh_data()

    def refresh_data(self) -> None:
        snap = self.runtime.resources.snapshot()
        self.cpu_bar.setValue(int(snap["cpu_percent"]))
        self.ram_bar.setValue(int(snap["ram_percent"]))
        self.disk_bar.setValue(int(snap["storage_percent"]))
        procs = self.runtime.resources.list_top_processes(limit=12)
        self.proc_table.setRowCount(len(procs))
        for i, p in enumerate(procs):
            self.proc_table.setItem(i, 0, QTableWidgetItem(str(p["pid"])))
            self.proc_table.setItem(i, 1, QTableWidgetItem(p["name"]))
            self.proc_table.setItem(i, 2, QTableWidgetItem(str(p["cpu_percent"])))
            self.proc_table.setItem(i, 3, QTableWidgetItem(str(p["memory_mb"])))
            self.proc_table.setItem(i, 4, QTableWidgetItem(p["status"]))


# ---------------------------------------------------------------------------
# 12. SECURITY CENTER
# ---------------------------------------------------------------------------
class SecurityCenterScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("SECURITY, PERMISSION & PAYMENT ISOLATION CENTER", "Persistent Autonomy Profiles, Instant Revocation & Mandatory Financial Boundary"))

        prof_row = QHBoxLayout()
        self.prof_combo = QComboBox()
        for k, v in self.runtime.permissions.list_profiles().items():
            self.prof_combo.addItem(v["label"], k)
        apply_btn = QPushButton("Apply Profile")
        apply_btn.setObjectName("PrimaryButton")
        apply_btn.clicked.connect(self._apply_profile)
        revoke_btn = QPushButton("Revoke All Permissions Immediately")
        revoke_btn.setObjectName("EmergencyButton")
        revoke_btn.clicked.connect(self._revoke_all)
        release_pay_btn = QPushButton("Release Payment Lockdown")
        release_pay_btn.clicked.connect(self._release_payment)
        prof_row.addWidget(self.prof_combo, 1)
        prof_row.addWidget(apply_btn)
        prof_row.addWidget(release_pay_btn)
        prof_row.addWidget(revoke_btn)
        root.addLayout(prof_row)

        perm_card, perm_lay = _make_card("Granular Permission Categories")
        perm_grid = QGridLayout()
        self.perm_checks: dict[str, QCheckBox] = {}
        grants = self.runtime.permissions.get_grants()
        for idx, (cat, val) in enumerate(sorted(grants.items())):
            cb = QCheckBox(cat.replace("_", " ").title())
            cb.setChecked(val)
            cb.toggled.connect(lambda checked, c=cat: self.runtime.permissions.set_permission(c, checked))
            self.perm_checks[cat] = cb
            perm_grid.addWidget(cb, idx // 3, idx % 3)
        perm_lay.addLayout(perm_grid)
        root.addWidget(perm_card)

        self.audit_table = QTableWidget(0, 5)
        self.audit_table.setHorizontalHeaderLabels(["Timestamp", "Event", "Category", "Decision", "Redacted Details"])
        self.audit_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.audit_table, 1)
        self.refresh_data()

    def _apply_profile(self) -> None:
        self.runtime.permissions.apply_profile(self.prof_combo.currentData())
        self.refresh_data()

    def _revoke_all(self) -> None:
        self.runtime.permissions.revoke_all_permissions()
        self.refresh_data()

    def _release_payment(self) -> None:
        self.runtime.payment_shield.release_user_completed_payment()
        self.refresh_data()

    def refresh_data(self) -> None:
        grants = self.runtime.permissions.get_grants()
        for cat, cb in self.perm_checks.items():
            cb.blockSignals(True)
            cb.setChecked(bool(grants.get(cat, False)))
            cb.blockSignals(False)
        events = self.runtime.audit.list_events(limit=40)
        self.audit_table.setRowCount(len(events))
        for i, ev in enumerate(events):
            self.audit_table.setItem(i, 0, QTableWidgetItem(ev["created_at"][:19]))
            self.audit_table.setItem(i, 1, QTableWidgetItem(ev["event_type"]))
            self.audit_table.setItem(i, 2, QTableWidgetItem(ev["category"]))
            self.audit_table.setItem(i, 3, QTableWidgetItem(ev["decision"]))
            self.audit_table.setItem(i, 4, QTableWidgetItem(ev["details_redacted"]))


# ---------------------------------------------------------------------------
# 13. PLUGIN MANAGER
# ---------------------------------------------------------------------------
class PluginManagerScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("EXTENSIBLE PLUGIN & SKILLS MANAGER", "Enable/Disable Skills, Run Isolated Executions & Load Custom Plugins"))

        ctrl_row = QHBoxLayout()
        run_btn = QPushButton("Execute Selected Skill")
        run_btn.setObjectName("PrimaryButton")
        run_btn.clicked.connect(self._run_selected)
        toggle_btn = QPushButton("Toggle Enable/Disable")
        toggle_btn.clicked.connect(self._toggle_selected)
        reload_btn = QPushButton("Discover User Plugins")
        reload_btn.clicked.connect(lambda: self.runtime.plugins.discover_user_plugins() or self.refresh_data())
        ctrl_row.addWidget(run_btn)
        ctrl_row.addWidget(toggle_btn)
        ctrl_row.addWidget(reload_btn)
        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        self.skill_table = QTableWidget(0, 5)
        self.skill_table.setHorizontalHeaderLabels(["Skill ID", "Name", "Version", "Enabled", "Description"])
        self.skill_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        root.addWidget(self.skill_table, 1)

        self.skill_out = QPlainTextEdit()
        self.skill_out.setReadOnly(True)
        self.skill_out.setMaximumHeight(130)
        root.addWidget(self.skill_out)
        self.refresh_data()

    def _selected_id(self) -> str | None:
        row = self.skill_table.currentRow()
        if row < 0 and self.skill_table.rowCount() > 0:
            row = 0
        item = self.skill_table.item(row, 0) if row >= 0 else None
        return item.text() if item else None

    def _run_selected(self) -> None:
        sid = self._selected_id()
        if sid:
            res = self.runtime.plugins.execute_skill(sid)
            self.skill_out.setPlainText(json.dumps(res, indent=2))

    def _toggle_selected(self) -> None:
        sid = self._selected_id()
        if sid:
            info = self.runtime.plugins.get_skill_info(sid)
            self.runtime.plugins.set_enabled(sid, not info["enabled"])
            self.refresh_data()

    def refresh_data(self) -> None:
        skills = self.runtime.plugins.list_skills()
        self.skill_table.setRowCount(len(skills))
        for i, s in enumerate(skills):
            self.skill_table.setItem(i, 0, QTableWidgetItem(s["skill_id"]))
            self.skill_table.setItem(i, 1, QTableWidgetItem(s["name"]))
            self.skill_table.setItem(i, 2, QTableWidgetItem(s["version"]))
            self.skill_table.setItem(i, 3, QTableWidgetItem("ENABLED" if s["enabled"] else "DISABLED"))
            self.skill_table.setItem(i, 4, QTableWidgetItem(s["description"]))


# ---------------------------------------------------------------------------
# 14. SETTINGS
# ---------------------------------------------------------------------------
class SettingsScreen(QWidget):
    def __init__(self, runtime: NexusUltronRuntime) -> None:
        super().__init__()
        self.runtime = runtime
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.addWidget(_make_heading("SYSTEM SETTINGS, CONNECTIVITY & BACKUP", "Hybrid Mode Policy, OAuth2 Setup & Database Backup/Restore"))

        mode_card, mode_lay = _make_card("Hybrid Offline / Online Mode Policy")
        mrow = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["automatic", "manual_offline", "manual_online"])
        self.mode_combo.setCurrentText(self.runtime.connectivity.policy)
        apply_mode_btn = QPushButton("Apply Connectivity Mode")
        apply_mode_btn.setObjectName("PrimaryButton")
        apply_mode_btn.clicked.connect(self._apply_mode)
        mrow.addWidget(QLabel("Operating Mode Policy:"))
        mrow.addWidget(self.mode_combo)
        mrow.addWidget(apply_mode_btn)
        mrow.addStretch()
        mode_lay.addLayout(mrow)
        root.addWidget(mode_card)

        bk_card, bk_lay = _make_card("SQLite Database & Memory Backup / Export")
        brow = QHBoxLayout()
        backup_btn = QPushButton("Create Verified Database Backup")
        backup_btn.clicked.connect(self._backup_db)
        export_btn = QPushButton("Export Memory JSON Bundle")
        export_btn.clicked.connect(self._export_mem)
        brow.addWidget(backup_btn)
        brow.addWidget(export_btn)
        brow.addStretch()
        bk_lay.addLayout(brow)
        root.addWidget(bk_card)

        self.status_box = QPlainTextEdit()
        self.status_box.setReadOnly(True)
        root.addWidget(self.status_box, 1)
        self.refresh_data()

    def _apply_mode(self) -> None:
        pol = self.mode_combo.currentText()
        self.runtime.config.set("mode_policy", pol)
        st = self.runtime.connectivity.set_policy(pol)
        self.status_box.setPlainText(json.dumps(st, indent=2))

    def _backup_db(self) -> None:
        dst = self.runtime.data_root / "backups" / "nexus_ultron_backup.db"
        self.runtime.db.backup_to(dst)
        self.status_box.setPlainText(f"SQLite backup verified at: {dst}")

    def _export_mem(self) -> None:
        dst = self.runtime.data_root / "backups" / "memory_export.json"
        self.runtime.memory.export_memory_bundle(dst)
        self.status_box.setPlainText(f"Memory bundle exported to: {dst}")

    def refresh_data(self) -> None:
        self.status_box.setPlainText(json.dumps(self.runtime.config.as_dict(), indent=2))
