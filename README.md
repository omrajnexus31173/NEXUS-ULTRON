# NEXUS ULTRON — Autonomous Personal AI Operating System

**Version:** 3.0.0 · **Target:** Windows 10 64-bit · **Tagline:** ONE MIND. INFINITE CAPABILITIES.

NEXUS ULTRON is a complete, self-contained personal AI operating system that runs **entirely offline** by default, with optional online mode. It combines a local AI reasoning kernel, a 12-agent multi-agent orchestration engine, an autonomous software development engine, voice I/O, file/document intelligence, browser automation, Gmail OAuth, SQLite memory, a PySide6 desktop dashboard, and a FastAPI Web Command Center — all wrapped in a hardened security layer that never touches payments, never logs secrets, and never accesses your personal Chrome profile.

---

## Highlights

- **Hybrid offline/online operation** with automatic/manual switching, hysteresis (anti-flap), and state preservation.
- **14-screen PySide6 desktop dashboard** (dark obsidian/navy/cyan theme): Home, AI Conversation, Voice Assistant, Task Center, Agent Center, Browser Center, AI Model Center, Memory Center, File Intelligence, Developer Center, System Monitor, Security Center, Plugin Manager, Settings.
- **FastAPI Web Command Center** (`--web --host 0.0.0.0 --port 8765`) — same capabilities from a browser.
- **Multi-Agent Engine:** 12 specialized agents + dynamic registration, parallel DAG execution, resource-aware queuing, persistent task states (`Pending` → `Planning` → `Running` → `Waiting` → `Failed`/`Completed`/`Cancelled`).
- **Autonomous Software Development Engine:** requirements → architecture → scaffolding → codegen (Python, C/C++, Java, JS/TS, HTML/CSS, SQL) → isolated venvs → testing → self-debugging → ZIP packaging.
- **SQLite Memory & Knowledge System:** WAL mode, separated temporary/long-term/project/sensitive stores, FTS5 + semantic search, CRUD, import/export, backup/restore, corruption recovery.
- **Voice & Conversation Engine:** wake-word, configurable phrase, push-to-talk, VAD, interruptible TTS, text fallback.
- **Mandatory Payment & Financial Isolation Engine:** layered URL/DOM/window/screen-capture blocking; **fail closed** when uncertain.
- **Security:** persistent permission profiles, emergency stop, audit log hash chain, Windows Credential Manager + encrypted config, prompt-injection & shell-command policy validation, plugin fault isolation.
- **One-click Windows Installer:** hardware/deps/DB/shortcut/health-check, install/update/repair/uninstall with data-retention choice, portable mode, NSIS/Inno/PyInstaller specs, GitHub Actions release pipeline.
- **Brand Identity Kit:** 5 logo variations + SVG + Windows `.ico`.

---

## Hardware Targets

| Tier | RAM | Storage | GPU | Use |
|------|-----|---------|-----|-----|
| Lightweight | 8 GB | 400 GB | Not required | Baseline target |
| Balanced | 12 GB | 400 GB | Not required | Standard desktop |
| Enhanced | 16 GB | 400 GB | Not required | Heavier local models |
| High-Performance | 32+ GB | 400 GB | Not required | Maximum concurrency |

The application auto-detects the tier and adjusts concurrency, local-model slots, and preloading accordingly. On an 8 GB baseline it starts in **~74 ms** with zero heavy models preloaded.

---

## Quick Start (Windows 10)

1. Run `installer\windows\Install-NexusUltron.bat` (or the NSIS/Inno installer) — it checks CPU/RAM/storage, installs dependencies, initializes the SQLite DB, creates shortcuts, and runs a health check.
2. Launch: `run_ultron.py` (desktop) or `run_ultron.py --web --host 0.0.0.0 --port 8765` (Web Command Center).
3. First-run health check: `run_ultron.py --health-check`.

### From source (any platform)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
# headless Linux: Qt shims self-heal automatically via nexus_ultron/core/qt_shim_builder.py
python run_ultron.py --health-check
python run_ultron.py --web --host 0.0.0.0 --port 8765
```

---

## Modes

- **Offline Mode:** local inference/reasoning, offline STT/TTS, memory, app launch, file/folder search & edit, PDF/TXT/DOCX/XLSX processing, calculations, notes/reminders, local project runner, system monitoring, desktop automation, tasks.
- **Online Mode:** cloud AI, web research, docs research, browser automation, Gmail OAuth, cloud execution.
- Switching is automatic (with hysteresis) or manual; state is preserved across switches.

---

## Security Guarantees

- Payment/financial workflows are **blocked at every layer** (URL, DOM, window, process, screen capture) and **fail closed** when detection is uncertain. No payment credentials are ever stored.
- Passwords, tokens, and OTPs are **never logged**. OTPs are never returned in plaintext; mobile-only MFA/CAPTCHA prompts user intervention.
- Your personal Chrome profile/bookmarks/cookies/passwords are **never touched** — an isolated ULTRON Chrome profile is used.
- Audit log maintains a cryptographic hash chain; integrity is verified on startup.

---

## Release Deliverables (`releases/`)

- `NEXUS-ULTRON-v3.0.0-Windows10-x64-Installer.zip` — one-click Windows installer bundle
- `NEXUS-ULTRON-v3.0.0-Windows10-x64-Portable.zip` — pre-initialized portable edition
- `NEXUS-ULTRON-v3.0.0-Brand-Identity-Kit.zip` — brand assets
- `SHA256SUMS.json` — cryptographic checksums manifest

Build with: `python installer/build_release.py`

---

## Verification

- **30 mandatory QA scenarios** automated under `tests/` via `pytest` — all pass (install/lifecycle, offline/online modes, hardware tiers, local/cloud AI, voice, files/documents/PDF, isolated browser, Gmail OAuth+OTP, multi-agent + failure recovery, autonomous dev engine, payment isolation, permissions, desktop UI + Web Command Center API).
- `run_ultron.py --health-check` reports `HEALTHY`.

```
python -m pytest tests/ -q        # 21/21 pass, covering all 30 scenarios
run_ultron.py --health-check      # HEALTHY, v3.0.0
```

---

## Documentation (`docs/`)

| Guide | File |
|-------|------|
| Installation Guide | `docs/Installation_Guide.md` |
| User Manual | `docs/User_Manual.md` |
| Troubleshooting Guide | `docs/Troubleshooting_Guide.md` |
| Architecture Documentation | `docs/Architecture_Documentation.md` |
| Security Documentation | `docs/Security_Documentation.md` |
| API Integration Guide | `docs/API_Integration_Guide.md` |
| Developer Extension Guide | `docs/Developer_Extension_Guide.md` |
| Backup & Recovery Guide | `docs/Backup_and_Recovery_Guide.md` |
| Release Notes | `docs/Release_Notes.md` |

---

## Brand

Palette: Obsidian Black `#05070B`, Midnight Navy `#0B1220`, Electric Cyan `#00D9FF`, Titanium Silver `#B9C5D0`.

5 logo variations in `assets/branding/`: primary horizontal, standalone emblem, square app icon, monochrome B&W, transparent background — plus `.svg` and Windows `.ico`.

---

**NEXUS ULTRON v3.0.0 — One Mind. Infinite Capabilities.**
