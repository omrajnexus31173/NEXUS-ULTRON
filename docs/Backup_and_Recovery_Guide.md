# NEXUS ULTRON — Backup & Recovery Guide

**Version:** 3.0.0

---

## 1. What Is Backed Up

NEXUS ULTRON stores all user data in `user_data/`:
- `nexus_ultron.db` — SQLite database (memory, conversations, permissions, projects, plugins) in WAL mode.
- `config.json` — user configuration.
- Logs and audit trail.

Backups cover the SQLite DB, config, and user files. The brand kit, application code, and installer are **not** part of user data (they can be re-installed).

---

## 2. Database Backup / Restore

The storage layer (`nexus_ultron/storage/database.py`) supports:

```python
backup_path = runtime.db.backup_to("/path/to/backup.sqlite")
# ...
runtime.db.restore_from(backup_path)
```

Backups are consistent (WAL mode + checkpoint) and can be restored at any time.

---

## 3. Corruption Recovery

If the SQLite DB file is corrupted:
1. The database is automatically detected as corrupt on open.
2. It is quarantined (renamed) and a fresh DB is initialized from migrations `001`–`003`.
3. If a backup exists, it is restored automatically; otherwise the system starts with an empty DB and logs the event.

Config corruption (`config.json`) is similarly detected and recovered from the bundled default config.

---

## 4. Uninstall with Data Retention

Running `installer\windows\Uninstall-Ultron.bat` prompts:

- **Retain user data:** `user_data/` (DB, config, logs) is preserved. A future reinstall resumes with your memory and settings intact.
- **Remove user data:** All local NEXUS ULTRON user data is deleted. This is irreversible.

---

## 5. Portable Mode Backup

In portable mode, `user_data/` lives alongside the executable. Copy the entire portable folder to back it up; restore by copying it back.

---

## 6. Recommended Backup Routine

1. Before an update or repair: `runtime.db.backup_to(...)`.
2. Periodically: copy `user_data/` to external storage.
3. Before uninstall: choose **retain** if you plan to reinstall.

---

## 7. What to Do on Data Loss

- If `nexus_ultron.db` is missing but a backup exists: restore via `restore_from()`.
- If no backup: the system re-initializes an empty DB; prior memory/conversations are unrecoverable.
- Always verify the audit chain after recovery (`audit.verify_integrity()`).
