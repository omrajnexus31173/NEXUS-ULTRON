"""SQLite WAL database engine with automatic migrations, backup/restore, and corruption recovery."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger("nexus_ultron.database")


class DatabaseManager:
    """Thread-safe SQLite manager with WAL mode, migrations, and self-healing recovery."""

    def __init__(self, db_path: Path, migrations_dir: Path, max_db_size_mb: int = 512) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = Path(migrations_dir)
        self.max_db_size_mb = max_db_size_mb
        self._lock = threading.RLock()
        self.recovered_from_corruption = False
        self._initialize_or_recover()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    @staticmethod
    def _move_file_with_retry(src: Path, dst: Path, max_attempts: int = 5, base_delay: float = 0.2) -> None:
        """Move a file with bounded retries for transient Windows file locks.

        On Windows, a file cannot be moved while another process holds an open
        handle to it.  We checkpoint WAL, close all connections, then retry the
        move with short backoff so transient locks are released.
        """
        last_exc: OSError | None = None
        for attempt in range(max_attempts):
            try:
                shutil.move(str(src), str(dst))
                return
            except (PermissionError, OSError) as exc:
                last_exc = exc
                if attempt == max_attempts - 1:
                    break
                time.sleep(base_delay * (attempt + 1))
        if last_exc is not None:
            raise last_exc


    def _initialize_or_recover(self) -> None:
        with self._lock:
            if self.db_path.exists() and self.db_path.stat().st_size > 0:
                conn: sqlite3.Connection | None = None
                try:
                    conn = self._connect()
                    # Checkpoint WAL before any file operations so sidecar files
                    # can be moved cleanly on Windows.
                    try:
                        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    except sqlite3.DatabaseError:
                        pass  # WAL may not exist or be uncheckpointable
                    res = conn.execute("PRAGMA quick_check;").fetchone()
                    if not res or res[0] != "ok":
                        raise sqlite3.DatabaseError(f"Integrity check failed: {res[0] if res else 'empty'}")
                except sqlite3.DatabaseError as exc:
                    # Always close the connection before touching filesystem
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass
                        conn = None

                    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    corrupt_backup = self.db_path.with_name(f"{self.db_path.name}.corrupted.{ts}.bak")

                    # Move the main database file with retries for Windows locks
                    self._move_file_with_retry(self.db_path, corrupt_backup)

                    # Move WAL and SHM sidecar files alongside the main DB
                    for suffix in ("-wal", "-shm"):
                        sidecar = self.db_path.with_name(self.db_path.name + suffix)
                        if sidecar.exists():
                            sidecar_bak = sidecar.with_name(f"{sidecar.name}.corrupted.{ts}.bak")
                            try:
                                self._move_file_with_retry(sidecar, sidecar_bak)
                            except (PermissionError, OSError):
                                pass  # Sidecar files are non-critical

                    logger.error(
                        "Corrupted SQLite database detected (%s). Quarantined to %s and reinitializing clean DB.",
                        exc,
                        corrupt_backup.name,
                    )
                    self.recovered_from_corruption = True

            self.apply_migrations()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def apply_migrations(self) -> list[str]:
        applied_now: list[str] = []
        if not self.migrations_dir.exists():
            return applied_now

        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                """
            )
            existing = {
                int(row["version"])
                for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
            }

            for sql_file in sorted(self.migrations_dir.glob("*.sql")):
                prefix = sql_file.stem.split("_", 1)[0]
                if not prefix.isdigit():
                    continue
                version = int(prefix)
                if version in existing:
                    continue
                script = sql_file.read_text(encoding="utf-8")
                conn.executescript(script)
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, sql_file.name, datetime.now(timezone.utc).isoformat()),
                )
                applied_now.append(sql_file.name)
                logger.info("Applied database migration: %s", sql_file.name)
        return applied_now

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        with self.connection() as conn:
            cur = conn.execute(sql, params)
            return cur.rowcount

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def backup_to(self, backup_path: Path) -> Path:
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            src = self._connect()
            dst = sqlite3.connect(str(backup_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        logger.info("Database backup saved to %s", backup_path)
        return backup_path

    def restore_from(self, backup_path: Path) -> None:
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        with self._lock:
            src = sqlite3.connect(str(backup_path))
            res = src.execute("PRAGMA quick_check;").fetchone()
            if not res or res[0] != "ok":
                src.close()
                raise sqlite3.DatabaseError("Backup file failed SQLite integrity check")
            dst = self._connect()
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
        self.apply_migrations()
        logger.info("Database restored from %s", backup_path)

    def enforce_growth_limits(self) -> dict[str, Any]:
        """Prune old temporary context and compact database if approaching size cap."""
        size_mb = round(self.db_path.stat().st_size / (1024 * 1024), 2) if self.db_path.exists() else 0.0
        pruned = 0
        if size_mb >= self.max_db_size_mb * 0.85:
            with self.connection() as conn:
                cur = conn.execute("DELETE FROM memory_entries WHERE namespace = 'temporary'")
                pruned = cur.rowcount
            with self._lock:
                conn = self._connect()
                conn.execute("VACUUM;")
                conn.close()
        return {"db_size_mb": size_mb, "temporary_entries_pruned": pruned}
