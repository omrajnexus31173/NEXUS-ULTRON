# NEXUS ULTRON — Architecture Documentation

**Version:** 3.0.0

---

## 1. System Overview

NEXUS ULTRON is a monorepo Python application (`v3.0.0`) built around a central runtime kernel (`NexusUltronRuntime`) that integrates 16 subsystems. It targets Windows 10 64-bit but is developed and verified on Linux with cross-platform abstractions preserving native Windows paths (WinVault keyring, pywinauto/UIA, SAPI5 TTS, PowerShell/NSIS/Inno/PyInstaller).

---

## 2. Runtime Kernel

`nexus_ultron/runtime.py` — `NexusUltronRuntime` is the single entrypoint. It constructs and wires all subsystems and exposes:
- `dashboard_overview()` — aggregate system status
- `connectivity` — offline/online mode manager
- `memory` — SQLite memory system
- `ai_router` — local/cloud AI provider routing
- `voice` — voice engine
- `browser` — browser engine
- `gmail` — Gmail OAuth/OTP
- `file_intel` — file intelligence
- `dev_engine` — autonomous software engine
- `orchestrator` — multi-agent DAG orchestrator
- `plugins` — plugin/skill manager
- `permissions` — permission engine
- `payment_shield` — payment isolation
- `prompt_shield` — prompt-injection guard
- `logging_engine` / `audit` — audit logger
- `resources` — hardware/resource manager
- `vault` — credential vault
- `planner` — task planner
- `shutdown()` — clean shutdown

---

## 3. Subsystems

### Core (`nexus_ultron/core/`)
- `logging_engine.py` — structured logging + audit event sink
- `hardware.py` — hardware tier detection (8/12/16/32 GB)
- `config_manager.py` — config with corruption self-healing
- `connectivity.py` — offline/online policy + hysteresis (anti-flap)
- `resource_manager.py` — CPU/RAM concurrency throttling
- `qt_shim_builder.py` — headless Linux Qt stub shim builder/pre-loader

### Storage (`nexus_ultron/storage/`)
- `database.py` — SQLite WAL, migrations `001`–`003`, corruption recovery, backup/restore
- `memory_system.py` — separated namespaces (temporary/long-term/project/sensitive), FTS5 + semantic search, CRUD, conversations, notes/reminders, import/export, `SensitiveMemoryError` blocker

### Security (`nexus_ultron/security/`)
- `audit_logger.py` — append-only audit log with hash-chain integrity
- `credential_vault.py` — encrypted secret storage (no raw passwords)
- `payment_isolation.py` — URL/DOM/window/process/screen-capture blocking, fail closed
- `permission_engine.py` — persistent profiles, emergency stop, shell-command policy, prompt-guard integration
- `prompt_guard.py` — prompt-injection neutralization for untrusted web/email content

### Intelligence (`nexus_ultron/intelligence/`)
- `file_intelligence.py` — DOCX/XLSX/PDF/TXT creation & extraction, spreadsheet analytics, safe calculator, file search
- `providers.py` — AI provider abstractions (local core, OpenAI-compatible)
- `planner.py` — task planner with checkpoint/resume

### Automation (`nexus_ultron/automation/`)
- `desktop_operator.py` — desktop automation (pywinauto/UIA abstraction)
- `browser_engine.py` — isolated Chrome + NEXUS Browser, tab/bookmark/download management
- `gmail_auth.py` — OAuth2 PKCE, OTP extraction/matching (never logged), mobile-MFA handoff

### Developer (`nexus_ultron/developer/`)
- `dev_engine.py` — multi-language codegen, isolated workspaces/venvs, testing, self-debugging with pre-modification backup, ZIP packaging

### Agents (`nexus_ultron/agents/`)
- `base_agent.py` — agent base class
- `builtin_agents.py` — 12 specialized agents
- `orchestrator.py` — dynamic parallel DAG orchestrator, agent registration, bounded retries

### Voice (`nexus_ultron/voice/`)
- `voice_engine.py` — wake-word, VAD, push-to-talk, offline STT, interruptible SAPI5/WAV TTS

### Plugins (`nexus_ultron/plugins/`)
- `plugin_manager.py` — modular skills, SQLite config, permission validation, fault isolation

### Desktop UI (`nexus_ultron/desktop_ui/`)
- `theme.py` — obsidian/navy/cyan theme
- `screens.py` — 14 screen specs
- `main_window.py` — PySide6 main window, all 14 screens, emergency stop

### Web UI (`nexus_ultron/web_ui/`)
- `server.py` — FastAPI REST backend + static/branding/releases mounts
- `static/` — `index.html`, `styles.css`, `app.js` (relative `/api/...` URLs)

### CLI / Launchers
- `run_ultron.py`, `NexusUltron.bat`, `nexus_ultron/cli.py` — unified CLI: desktop, web, health-check, single objective

### Installer (`installer/`)
- `lifecycle_manager.py` — 14-step install/update/repair/backup/restore/uninstall
- `build_release.py` — release bundle builder
- `windows/` — NSIS, Inno, PyInstaller specs, PowerShell/batch scripts
- `.github/workflows/build-windows-installer.yml` — Windows CI release pipeline

---

## 4. Data Flow

```
User Input (UI/Web/CLI)
        ↓
NexusUltronRuntime → Connectivity (mode) → Permissions/PaymentShield/PromptShield
        ↓
Subsystem (AI/Voice/Browser/File/Dev/Agent/Plugin)
        ↓
SQLite Memory (WAL) ←→ Audit Log (hash chain)
        ↓
Result rendered on Dashboard / Web API
```

All security checks (permissions, payment isolation, prompt guard) run **before** any action. Payment isolation fails closed.

---

## 5. Offline → Online Mode Switching

`connectivity.py` manages policy (`automatic` / `manual_online` / `manual_offline`):
- `automatic`: probes connectivity; two consecutive failures required to flip to offline (anti-flap hysteresis).
- State is preserved across mode switches.
- Manual Online degrades safely to Offline if internet is unreachable (never crashes).

---

## 6. Task / Workflow Lifecycle

`planner.py` + `orchestrator.py`:
- Task states: `Pending` → `Planning` → `Running` → `Waiting` → `Completed` / `Failed` / `Cancelled`.
- Steps execute on agents via a dependency DAG; resource-aware queuing (1 worker on 8 GB).
- Checkpoints are persisted; interrupted tasks resume on restart.
- Bounded retries per agent; unrecoverable failures mark the task `Failed` (never claimed completed).

---

## 7. Packaging & Delivery

- `installer/build_release.py` builds three ZIPs + `SHA256SUMS.json`.
- Windows installer: NSIS / Inno Setup / PowerShell / batch / PyInstaller.
- CI: `.github/workflows/build-windows-installer.yml` (Windows x64 release pipeline).
