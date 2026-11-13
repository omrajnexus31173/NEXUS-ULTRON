# NEXUS ULTRON — Troubleshooting Guide

**Version:** 3.0.0

---

## 1. Application Will Not Start

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `libGL.so.1: cannot open shared object file` (Linux headless) | Missing system OpenGL/EGL libs | Qt shims self-heal via `nexus_ultron/core/qt_shim_builder.py`; ensure `.venv/qt_shims/` exists and `LD_LIBRARY_PATH` points at it before launching. |
| `ImportError: PySide6` | PySide6 not installed | `pip install -r requirements.txt` |
| Health check returns unhealthy | Missing deps / DB not initialized | Re-run the installer; it installs deps and initializes migrations `001`–`003`. |

### Headless Linux Qt shims

On Linux without a GPU, PySide6 needs stub OpenGL/EGL/dbus libraries. NEXUS ULTRON ships `nexus_ultron/core/qt_shim_builder.py`, which compiles minimal symbol-matched C stubs into `.venv/qt_shims/` and pre-loads them automatically (called by `tests/conftest.py` and `nexus_ultron/cli.py`). No system GPU drivers are required.

---

## 2. Offline / Online Mode Issues

| Symptom | Fix |
|---------|-----|
| Stuck in Offline Mode despite internet | Automatic mode uses hysteresis: two consecutive failed probes are required to flip. Wait and retry, or set manual policy in Settings → Connectivity. |
| Manual Online Mode degrades to Offline | Internet is unreachable; this is intentional (safe degradation, never a crash). Restore connectivity and switch back to Manual Online. |
| Cloud AI fails | Falls back transparently to the local offline core. Verify `OPENAI_API_KEY` is set in the credential vault if using cloud. |

---

## 3. Voice Issues

| Symptom | Fix |
|---------|-----|
| Wake-word not detected | Speak the configured phrase clearly; check mic permissions in Settings → Voice. |
| No TTS audio | Offline TTS writes a WAV; verify speakers are enabled and the WAV path is writable. |
| Microphone unavailable | Use text fallback by typing in the AI Conversation screen. |

---

## 4. Browser / Gmail Issues

| Symptom | Fix |
|---------|-----|
| Chrome profile error | NEXUS ULTRON uses an isolated profile; it never touches your personal Chrome profile. Check the isolated profile dir in Browser Center. |
| Gmail OAuth fails | Use the PKCE authorization flow; grant `authorized_email_reading` + `otp_retrieval` permissions explicitly for test sessions. |
| OTP not matched | OTPs expire after 5 minutes; mobile-only MFA/CAPTCHA requires user intervention on the phone. |

---

## 5. Payment Isolation Blocks a Legitimate Action

Payment isolation **fail-closes** when detection is uncertain. If a non-payment action is blocked:
- Confirm the URL/DOM does not contain checkout, banking, UPI, or card fields.
- Review `Security Center → Payment Isolation` and the audit log.
- Contact support if a false positive persists; do not disable payment isolation.

---

## 6. Database Issues

| Symptom | Fix |
|---------|-----|
| DB corruption detected | The database is automatically quarantined and restored from the last backup (WAL mode + corruption recovery). |
| Missing memory after restart | Confirm user data was retained during uninstall/reinstall. |
| Slow queries | Run `VACUUM` on the SQLite DB; FTS5 indexes are maintained automatically. |

---

## 7. Agent / Task Failures

| Symptom | Fix |
|---------|-----|
| Task stuck in `Running` | An agent may have crashed. Restart the application — interrupted tasks resume from their last checkpoint. |
| Task `Failed` | Unrecoverable agent error after bounded retries. Review the audit log, then re-submit the task. |
| Multi-agent deadlock | Resource-aware queuing limits concurrency on low-RAM tiers (1 worker on 8 GB). |

---

## 8. Installer / Update / Repair / Uninstall

| Symptom | Fix |
|---------|-----|
| Installer says RAM/storage insufficient | Free up storage or add RAM; the 8 GB / 400 GB baseline is mandatory. |
| Update fails | Run `Repair-NexusUltron.bat` first, then retry the update. |
| Uninstall asks retain/remove | Choose **retain** to keep `user_data/` (memory, configs); choose **remove** to delete everything. |

---

## 9. Getting Help

- Run `run_ultron.py --health-check` and review the JSON output.
- Check the audit log in **Security Center → Audit Log**.
- Review logs under `user_data/logs/`.
- For persistent issues, export your memory and settings (retain user data), then reinstall.
