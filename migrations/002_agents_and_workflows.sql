-- Migration 002: Master Planner Tasks, Subtasks, Multi-Agent Runs & Browser History

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    objective TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general',
    priority INTEGER NOT NULL DEFAULT 5,
    complexity TEXT NOT NULL DEFAULT 'medium',
    state TEXT NOT NULL CHECK (state IN ('Pending', 'Planning', 'Running', 'Waiting', 'Failed', 'Completed', 'Cancelled')),
    mode_used TEXT NOT NULL DEFAULT 'offline',
    plan_json TEXT DEFAULT '[]',
    checkpoint_json TEXT DEFAULT '{}',
    result_summary TEXT DEFAULT '',
    verified INTEGER NOT NULL DEFAULT 0,
    error_message TEXT DEFAULT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state, priority DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS subtasks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    assigned_agent TEXT NOT NULL,
    depends_on_json TEXT DEFAULT '[]',
    state TEXT NOT NULL CHECK (state IN ('Pending', 'Planning', 'Running', 'Waiting', 'Failed', 'Completed', 'Cancelled')),
    output_json TEXT DEFAULT '{}',
    error_message TEXT DEFAULT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT DEFAULT NULL,
    completed_at TEXT DEFAULT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_subtasks_task ON subtasks(task_id, step_index);

CREATE TABLE IF NOT EXISTS desktop_execution_history (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_bookmarks (
    id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_history (
    id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL DEFAULT 'default',
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    blocked_by_payment_shield INTEGER NOT NULL DEFAULT 0,
    visited_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS browser_downloads (
    id TEXT PRIMARY KEY,
    profile_name TEXT NOT NULL DEFAULT 'default',
    url TEXT NOT NULL,
    file_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
