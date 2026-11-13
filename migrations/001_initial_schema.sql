-- Migration 001: Core Schema, Conversations, Preferences, Memory & FTS5 Knowledge Base

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    pref_key TEXT PRIMARY KEY,
    pref_value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    mode_used TEXT NOT NULL DEFAULT 'offline',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    provider TEXT DEFAULT 'ultron_local_core',
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, created_at);

CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL CHECK (namespace IN ('temporary', 'long_term', 'project', 'instruction', 'knowledge')),
    project_id TEXT DEFAULT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    tags_json TEXT DEFAULT '[]',
    embedding_json TEXT DEFAULT '[]',
    importance INTEGER DEFAULT 5,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memory_entries(namespace, project_id);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    entry_id UNINDEXED,
    title,
    content,
    tags
);

CREATE TABLE IF NOT EXISTS notes_reminders (
    id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL CHECK (item_type IN ('note', 'reminder')),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    due_at TEXT DEFAULT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    language TEXT NOT NULL,
    framework TEXT NOT NULL,
    status TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0,
    summary_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
