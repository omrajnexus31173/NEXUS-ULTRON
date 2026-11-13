# NEXUS ULTRON — User Manual

**Version:** 3.0.0

---

## 1. The 14 Dashboard Screens

| # | Screen | Purpose |
|---|--------|---------|
| 1 | **Home Dashboard** | System status, mode, hardware tier, recent activity, quick actions. |
| 2 | **AI Conversation** | Chat with the local/cloud AI. Supports calculations, reasoning, and task delegation. |
| 3 | **Voice Assistant** | Wake-word, push-to-talk, VAD, interruptible speech, mic configuration. |
| 4 | **Task Center** | Create, monitor, and manage autonomous tasks with persistent states. |
| 5 | **Agent Center** | View the 12 specialized agents, register custom agents, monitor DAG execution. |
| 6 | **Browser Center** | Isolated ULTRON Chrome profile, NEXUS Browser tabs, bookmarks, downloads. |
| 7 | **AI Model Center** | Manage local/cloud AI models, providers, and mode switching (offline/online). |
| 8 | **Memory Center** | Browse, search (FTS5/semantic), edit, delete, import/export memory entries. |
| 9 | **File Intelligence** | Create/read/edit DOCX, XLSX, PDF, TXT; spreadsheet analytics; safe calculator; notes/reminders. |
| 10 | **Developer Center** | Autonomous software generation, isolated workspaces, testing, packaging, self-debugging. |
| 11 | **System Monitor** | CPU, RAM, storage, battery, network, process health. |
| 12 | **Security Center** | Permission profiles, emergency stop, audit log, payment isolation status. |
| 13 | **Plugin Manager** | Install, configure, enable/disable skills; fault-isolated execution. |
| 14 | **Settings** | Mode policy, voice config, hardware profile, connectivity, security boundaries. |

Every button on every screen performs a real function. There are no decorative non-functional buttons.

---

## 2. AI Conversation

Type a request in the input field and press Send. Examples:
- `calculate (128 * 4) + 88`
- `Explain modular Python architecture`
- `Search my memory for offline sqlite authentication`

The system routes to the best available provider (local offline core in Offline Mode, cloud-compatible in Online Mode). Secrets such as OTPs are redacted before any cloud request.

---

## 3. Voice Assistant

- **Wake-word:** Say the configured phrase (default `hey ultron`) to activate.
- **Push-to-Talk:** Hold the mic button to speak.
- **VAD:** Voice activity detection automatically segments speech.
- **Interruptible TTS:** Click Emergency Stop or speak again to interrupt playback.
- **Text fallback:** If the microphone is unavailable, type instead.

Voice processing is fully offline (local STT + TTS). No audio is sent to the cloud.

---

## 4. Task Center & Agent Engine

Create a task with an objective. NEXUS ULTRON decomposes it into steps, assigns steps to specialized agents (research, code, QA, security, file ops, etc.), and executes them in a dependency-aware DAG.

Task states: `Pending` → `Planning` → `Running` → `Waiting` → `Completed` / `Failed` / `Cancelled`.

If an agent crashes, the system retries (bounded) and, if unrecoverable, marks the task `Failed` without corrupting other work. Interrupted tasks resume on restart.

---

## 5. Browser Center (Privacy-First)

- **Isolated ULTRON Chrome profile:** A dedicated profile directory is created. Your personal Chrome profile, bookmarks, history, cookies, and passwords are **never** read or copied.
- **NEXUS Browser:** Optional Chromium-based browser with separate profiles, bookmarks, history, and download manager.
- All browser automation runs in isolated tabs/profiles.

---

## 6. File Intelligence

Create and read documents offline:
- **TXT:** read/write with automatic `.bak` backup on edit.
- **DOCX:** create with title + paragraphs; extract text.
- **XLSX:** create spreadsheets; compute column sum/average/min/max.
- **PDF:** generate simple PDFs; extract multi-line text.
- **Calculator:** safe expression evaluation (`sqrt(144) + mean([10,20,30])` → `32.0`).

---

## 7. Developer Center (Autonomous Software Engine)

Describe an application in plain language and NEXUS ULTRON will:
1. Generate requirements & architecture.
2. Scaffold the project in an isolated workspace with its own venv.
3. Write code across Python, C/C++, Java, JS/TS, HTML/CSS, or SQL.
4. Run unit tests and a smoke test.
5. Self-debug if tests fail (with pre-modification backup).
6. Package the verified project as a ZIP.

Example: `Build me a complete inventory management application with authentication, billing, stock management, reporting, and an admin dashboard.`

---

## 8. Memory Center

Memory is stored in separated namespaces:
- **Temporary:** session-scratch, auto-expires.
- **Long-term:** persistent facts and preferences.
- **Project:** per-project context.
- **Sensitive:** blocked — credentials/card numbers cannot be silently stored (`SensitiveMemoryError`).

Search with full-text (FTS5) and semantic matching. Import/export and backup/restore are supported.

---

## 9. Security Center

- **Permission profiles:** persistent grants per category (browser, file access, dev tools, email, OTP, etc.).
- **Emergency Stop:** one-click kill-switch that halts all autonomous actions.
- **Audit log:** every security-relevant decision is logged with a cryptographic hash chain. Integrity is verified on startup.
- **Payment isolation:** all financial/payment URLs, DOM fields, banking windows, and screen captures are blocked. Fails closed when uncertain.

---

## 10. Plugin Manager (Skills)

Skills are modular capabilities with permission validation and fault isolation. Built-in skills include the security posture auditor, scientific calculator, and file intelligence. A failing skill cannot crash the host.

---

## 11. Safety Rules (Standing)

- Never access your personal Chrome profile.
- Never log or expose passwords, tokens, or OTPs.
- Never store payment credentials or run real financial transactions (simulated only).
- Payment/financial workflows are always blocked (fail closed).
