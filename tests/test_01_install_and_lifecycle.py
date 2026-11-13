"""QA Scenarios #1, #2, #26, #27, #30: Install, First Launch, Restart Resume, DB Persistence/Recovery & Uninstall."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from installer.lifecycle_manager import LifecycleManager
from nexus_ultron.core.config_manager import ConfigManager
from nexus_ultron.runtime import NexusUltronRuntime
from nexus_ultron.storage.database import DatabaseManager


def test_01_and_02_installation_and_first_launch(tmp_path: Path, repo_root: Path) -> None:
    """Test #1 (Application installation) & Test #2 (First launch)."""
    install_target = tmp_path / "installed_ultron"
    steps_seen: list[int] = []
    lm = LifecycleManager(repo_root)
    res = lm.install(
        install_target,
        portable_mode=False,
        simulated_ram_gb=8.0,
        progress_cb=lambda n, _m: steps_seen.append(n),
    )
    assert res["installed"] is True
    assert res["health_check_passed"] is True
    assert res["hardware_tier"] == "lightweight"
    assert 1 in steps_seen and 14 in steps_seen
    assert (install_target / "install_manifest.json").exists()
    assert (install_target / "shortcut_manifest.json").exists()

    # First launch from installed directory
    rt = NexusUltronRuntime(
        repo_root=install_target,
        data_root=install_target / "user_data",
        simulated_ram_gb=8.0,
        connectivity_probe_fn=lambda: False,
    )
    ov = rt.dashboard_overview()
    assert ov["availability"] == "OPERATIONAL"
    rt.shutdown()


def test_26_application_restart_and_workflow_resume(tmp_path: Path, repo_root: Path) -> None:
    """Test #26: Interrupted Running workflow persists checkpoint and resumes after restart."""
    data_dir = tmp_path / "restart_data"
    rt1 = NexusUltronRuntime(repo_root=repo_root, data_root=data_dir, connectivity_probe_fn=lambda: False)
    task = rt1.planner.create_task("Verify system telemetry after restart")
    # Simulate mid-execution crash where step 0 completed and step 1 was left 'Running'
    rt1.planner.update_task_state(task["id"], "Running", checkpoint={"artifacts": {"step0": "saved"}})
    rt1.planner.update_subtask(task["subtasks"][0]["id"], "Completed", output={"ok": True})
    rt1.planner.update_subtask(task["subtasks"][1]["id"], "Running")
    rt1.shutdown()

    # Restart application -> interrupted task must be recovered to Pending with step 0 still Completed!
    rt2 = NexusUltronRuntime(repo_root=repo_root, data_root=data_dir, connectivity_probe_fn=lambda: False)
    assert any(t["id"] == task["id"] for t in rt2.resumable_tasks)
    completed = rt2.orchestrator.execute_task(task["id"])
    assert completed["state"] == "Completed"
    assert completed["verified"] is True
    rt2.shutdown()


def test_27_database_persistence_backup_and_corruption_recovery(tmp_path: Path, repo_root: Path) -> None:
    """Test #27: SQLite persistence across restarts, backup/restore, plus corrupted DB & config self-healing."""
    data_dir = tmp_path / "db_persist"
    rt1 = NexusUltronRuntime(repo_root=repo_root, data_root=data_dir, connectivity_probe_fn=lambda: False)
    rt1.memory.set_preference("preferred_language", "Python")
    mem = rt1.memory.add_memory("Architecture Rule", "Always isolate payment workflows", namespace="long_term")
    backup_file = rt1.db.backup_to(tmp_path / "backup.sqlite")
    rt1.shutdown()

    # Verify persistence on clean reopen
    rt2 = NexusUltronRuntime(repo_root=repo_root, data_root=data_dir, connectivity_probe_fn=lambda: False)
    assert rt2.memory.get_preference("preferred_language") == "Python"
    assert rt2.memory.get_memory(mem["id"])["title"] == "Architecture Rule"
    rt2.shutdown()

    # Corrupt config.json and verify automatic recovery
    corrupt_cfg_path = data_dir / "config.json"
    corrupt_cfg_path.write_text("{broken json!!!", encoding="utf-8")
    cfg = ConfigManager(repo_root / "config" / "default_config.json", corrupt_cfg_path)
    assert cfg.recovered_from_corruption is True
    assert cfg.get("app_name") == "NEXUS ULTRON"

    # Corrupt SQLite file and verify quarantine + restore from backup
    bad_db_path = tmp_path / "corrupt_test" / "nexus_ultron.db"
    bad_db_path.parent.mkdir(parents=True, exist_ok=True)
    bad_db_path.write_bytes(b"NOT_A_VALID_SQLITE_HEADER_CORRUPTED_BYTES" * 20)
    recovered_db = DatabaseManager(bad_db_path, repo_root / "migrations")
    assert recovered_db.recovered_from_corruption is True
    recovered_db.restore_from(backup_file)
    rows = recovered_db.query_all("SELECT title FROM memory_entries WHERE id = ?", (mem["id"],))
    assert len(rows) == 1 and rows[0]["title"] == "Architecture Rule"


def test_30_complete_uninstallation_retain_and_remove_options(tmp_path: Path, repo_root: Path) -> None:
    """Test #30: Uninstall retaining user_data vs removing all user_data."""
    lm = LifecycleManager(repo_root)

    dir_retain = tmp_path / "ultron_retain"
    lm.install(dir_retain, simulated_ram_gb=8.0)
    res_keep = lm.uninstall(dir_retain, retain_user_data=True)
    assert res_keep["uninstalled"] is True and res_keep["user_data_retained"] is True
    assert (dir_retain / "user_data" / "nexus_ultron.db").exists()
    assert not (dir_retain / "run_ultron.py").exists()

    dir_wipe = tmp_path / "ultron_wipe"
    lm.install(dir_wipe, simulated_ram_gb=8.0)
    res_wipe = lm.uninstall(dir_wipe, retain_user_data=False)
    assert res_wipe["uninstalled"] is True and res_wipe["user_data_retained"] is False
    assert not dir_wipe.exists()


def test_database_corruption_recovery_with_active_connections(tmp_path: Path, repo_root: Path) -> None:
    """Windows regression: _initialize_or_recover() must close active connections/cursors,
    checkpoint WAL, handle -wal/-shm sidecars, preserve corrupted DB as timestamped backup,
    recreate database and reapply migrations — without silently deleting user data."""
    db_path = tmp_path / "active_conn_test.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Create a valid database with user data
    db1 = DatabaseManager(db_path, repo_root / "migrations")
    db1.execute(
        "INSERT INTO memory_entries (id, namespace, title, content, tags_json, embedding_json, importance, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("mem-1", "long_term", "Important Rule", "Never mix payment flows", "[]", "[]", 5, "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    )
    assert db1.recovered_from_corruption is False

    # 2. Hold an active connection (simulating a leaked cursor/connection on Windows)
    active_conn = sqlite3.connect(str(db_path))
    active_conn.execute("CREATE TABLE IF NOT EXISTS active_table (id INTEGER PRIMARY KEY)")
    active_conn.execute("INSERT INTO active_table (id) VALUES (1)")
    # Intentionally NOT closing active_conn — simulates a connection left open

    # 3. Corrupt the database file externally
    db_path.write_bytes(b"NOT_A_VALID_SQLITE_FILE_CORRUPTED_BYTES" * 100)

    # 4. Create WAL/SHM sidecar files to verify they are handled alongside the main DB
    (db_path.parent / (db_path.name + "-wal")).write_bytes(b"wal-sidecar-data")
    (db_path.parent / (db_path.name + "-shm")).write_bytes(b"shm-sidecar-data")

    # 5. New DatabaseManager must recover: close connections, move corrupted files,
    #    recreate clean DB, reapply migrations
    recovered = DatabaseManager(db_path, repo_root / "migrations")
    assert recovered.recovered_from_corruption is True

    # 6. Corrupted DB preserved as timestamped backup (never silently deleted)
    bak_files = list(tmp_path.glob("active_conn_test.db.corrupted.*.bak"))
    assert len(bak_files) >= 1, "Corrupted DB must be preserved as timestamped backup"

    # 7. WAL/SHM sidecars also backed up
    sidecar_bak = list(tmp_path.glob("active_conn_test.db-*.corrupted.*.bak"))
    assert len(sidecar_bak) >= 1, "WAL/SHM sidecars must be handled during recovery"

    # 8. New database is functional with all migrations applied
    tables = recovered.query_all("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = {r["name"] for r in tables}
    assert "schema_migrations" in table_names
    assert "memory_entries" in table_names
    assert "permission_grants" in table_names

    active_conn.close()
    assert recovered.recovered_from_corruption is True
