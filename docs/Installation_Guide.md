# NEXUS ULTRON — Installation Guide

**Version:** 3.0.0 · **Target OS:** Windows 10 64-bit

---

## 1. Supported Hardware Tiers

| Tier | RAM | Storage | GPU | Notes |
|------|-----|---------|-----|-------|
| Lightweight | 8 GB | 400 GB | Not required | Baseline target |
| Balanced | 12 GB | 400 GB | Not required | Standard desktop |
| Enhanced | 16 GB | 400 GB | No dedicated GPU required | Heavier local models |
| High-Performance | 32+ GB | 400 GB | Not required | Maximum concurrency |

The installer performs a pre-flight check for CPU, RAM, storage, and Windows version before proceeding.

---

## 2. Installation Methods

### A. One-Click Installer (Recommended)

Run `installer\windows\Install-NexusUltron.bat` as Administrator. It:

1. Checks Windows 10 64-bit, CPU, RAM, and free storage.
2. Installs the Python runtime and dependencies.
3. Initializes the SQLite database (migrations `001`–`003`).
4. Creates Start Menu + desktop shortcuts.
5. Runs a first-launch health check.
6. Launches NEXUS ULTRON.

Alternative installer front-ends:
- `installer\windows\NexusUltronSetup.ps1` (PowerShell)
- `installer\windows\nexus_ultron_installer.nsi` (NSIS)
- `installer\windows\nexus_ultron_inno.iss` (Inno Setup)
- `installer\windows\pyinstaller_nexus_ultron.spec` (PyInstaller single-file)

### B. Portable Mode

Run `installer\windows\Install-NexusUltron.bat` and choose **Portable Mode**, or extract `NEXUS-ULTRON-v3.0.0-Windows10-x64-Portable.zip`. No installation is required; all data lives alongside the executable.

### C. From Source

```bash
python -m venv .venv
. .venv\Scripts\activate
pip install -r requirements-windows.txt
python run_ultron.py --health-check
python run_ultron.py          # desktop dashboard
python run_ultron.py --web --host 0.0.0.0 --port 8765  # Web Command Center
```

---

## 3. Modes of Operation

- **Offline Mode (default):** Local inference/reasoning, offline STT/TTS, memory, file/folder search & edit, PDF/DOCX/XLSX processing, calculations, notes/reminders, local project runner, system monitoring, desktop automation, tasks.
- **Online Mode:** Cloud AI, web research, docs research, browser automation, Gmail OAuth, cloud execution.

Switching is automatic (with hysteresis) or manual. State is preserved across switches.

---

## 4. First Launch

After installation, the dashboard opens to the **Home** screen. The top bar shows:
- Current mode (Online/Offline)
- Hardware tier
- Emergency Stop button
- Settings shortcut

Run `run_ultron.py --health-check` at any time to verify system and security health.

---

## 5. Updating / Repairing

- `installer\windows\Update-NexusUltron.bat` — in-place update, preserving user data.
- `installer\windows\Repair-NexusUltron.bat` — reinstalls runtime/components without touching user data.

---

## 6. Uninstallation

Run `installer\windows\Uninstall-Ultron.bat`. You will be asked whether to **retain** or **remove** your user data (SQLite memory, configs, logs):

- **Retain:** Keeps `user_data/` so a future reinstall picks up your memory and settings.
- **Remove:** Deletes all local NEXUS ULTRON user data.

---

## 7. Verification

```bash
run_ultron.py --health-check
```

Expected output: `status: HEALTHY`, version `3.0.0`, audit chain valid, 12 registered agents, Chrome isolation verified.

---

## 8. Requirements

- Windows 10 64-bit (version 1903+)
- 8 GB RAM minimum (Lightweight tier)
- 400 GB free storage
- No dedicated GPU required
- Internet optional (required only for Online Mode / cloud features)
