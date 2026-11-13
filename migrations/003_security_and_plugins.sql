-- Migration 003: Security Audit Log, Permission Grants, Plugins & Payment Shield Events

CREATE TABLE IF NOT EXISTS permission_grants (
    category TEXT PRIMARY KEY,
    granted INTEGER NOT NULL DEFAULT 0,
    profile_source TEXT NOT NULL DEFAULT 'autonomous_operator',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    category TEXT NOT NULL,
    decision TEXT NOT NULL,
    details_redacted TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON security_audit_log(created_at DESC);

CREATE TABLE IF NOT EXISTS payment_isolation_events (
    id TEXT PRIMARY KEY,
    source_layer TEXT NOT NULL,
    trigger_reason TEXT NOT NULL,
    target_descriptor TEXT NOT NULL,
    action_taken TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plugins_registry (
    skill_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    permissions_json TEXT NOT NULL DEFAULT '[]',
    config_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    builtin INTEGER NOT NULL DEFAULT 1,
    module_path TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
