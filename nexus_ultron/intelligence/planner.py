"""Master Intelligence & Planning Engine (DAG Task Decomposition, Persistent Checkpoints & Verification)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from ..security.audit_logger import AuditLogger
from ..security.payment_isolation import PaymentIsolationEngine, PaymentIsolationTriggered
from ..storage.database import DatabaseManager

logger = logging.getLogger("nexus_ultron.planner")

TASK_STATES = ("Pending", "Planning", "Running", "Waiting", "Failed", "Completed", "Cancelled")


class MasterPlanner:
    """
    Central reasoning & planning layer:
      - Interprets natural-language instructions
      - Enforces Payment Isolation BEFORE creating/running plans
      - Decomposes objectives into explicit agent subtasks with dependencies
      - Persists task & subtask state + checkpoints to SQLite for crash/restart resume
      - Prevents infinite loops via bounded retry counters
      - Distinguishes attempted vs verified completion
    """

    def __init__(
        self,
        db: DatabaseManager,
        payment_shield: PaymentIsolationEngine,
        audit: AuditLogger,
    ) -> None:
        self.db = db
        self.payment_shield = payment_shield
        self.audit = audit

    def classify_and_decompose(self, objective: str) -> tuple[str, str, list[dict[str, Any]]]:
        """Classify objective into category, complexity, and ordered multi-agent subtask DAG."""
        verdict = self.payment_shield.inspect_objective(objective)
        if verdict.isolated:
            raise PaymentIsolationTriggered(f"Task rejected by Payment Isolation Engine: {verdict.reason}")

        lower = (objective or "").lower()

        if any(
            kw in lower
            for kw in (
                "build ",
                "develop ",
                "create a complete",
                "create an app",
                "inventory management",
                "web app",
                "application",
                "api ",
                "scaffold",
                "software",
            )
        ):
            category = "software_development"
            complexity = "high"
            steps = [
                {"step_index": 0, "title": "Analyze requirements & software architecture", "assigned_agent": "master_planning_agent", "depends_on": []},
                {"step_index": 1, "title": "Scaffold isolated workspace & generate full source code", "assigned_agent": "coding_agent", "depends_on": [0]},
                {"step_index": 2, "title": "Execute automated tests & self-heal any defects", "assigned_agent": "testing_agent", "depends_on": [1]},
                {"step_index": 3, "title": "Generate technical documentation & usage guide", "assigned_agent": "documentation_agent", "depends_on": [1]},
                {"step_index": 4, "title": "Verify runnable deliverable & package release archive", "assigned_agent": "qa_agent", "depends_on": [2, 3]},
            ]
            return category, complexity, steps

        if any(kw in lower for kw in ("otp", "verification email", "gmail")):
            category = "email_authentication"
            complexity = "medium"
            steps = [
                {"step_index": 0, "title": "Validate OAuth authorization & OTP permission policy", "assigned_agent": "master_planning_agent", "depends_on": []},
                {"step_index": 1, "title": "Scan authorized inbox & match active login session OTP", "assigned_agent": "email_agent", "depends_on": [0]},
                {"step_index": 2, "title": "Verify non-expired authentication state without log exposure", "assigned_agent": "qa_agent", "depends_on": [1]},
            ]
            return category, complexity, steps

        if any(kw in lower for kw in ("browser", "website", "chrome", "open url", "search web", "research")):
            category = "browser_and_research"
            complexity = "medium"
            steps = [
                {"step_index": 0, "title": "Plan safe research & verify URLs against Payment Shield", "assigned_agent": "master_planning_agent", "depends_on": []},
                {"step_index": 1, "title": "Execute isolated browser/research retrieval", "assigned_agent": "research_agent", "depends_on": [0]},
                {"step_index": 2, "title": "Synthesize & verify sanitized findings", "assigned_agent": "qa_agent", "depends_on": [1]},
            ]
            return category, complexity, steps

        if any(kw in lower for kw in ("spreadsheet", "excel", "xlsx", "csv", "analyze data")):
            category = "data_analysis"
            complexity = "medium"
            steps = [
                {"step_index": 0, "title": "Inspect dataset schema & metrics objective", "assigned_agent": "master_planning_agent", "depends_on": []},
                {"step_index": 1, "title": "Run statistical & spreadsheet computation", "assigned_agent": "data_analysis_agent", "depends_on": [0]},
                {"step_index": 2, "title": "Verify computed metrics accuracy", "assigned_agent": "qa_agent", "depends_on": [1]},
            ]
            return category, complexity, steps

        if any(kw in lower for kw in ("pdf", "docx", "file", "folder", "document")):
            category = "file_operations"
            complexity = "low"
            steps = [
                {"step_index": 0, "title": "Execute authorized file/document operation", "assigned_agent": "file_management_agent", "depends_on": []},
                {"step_index": 1, "title": "Verify output artifact integrity on disk", "assigned_agent": "qa_agent", "depends_on": [0]},
            ]
            return category, complexity, steps

        category = "general_autonomous_task"
        complexity = "low"
        steps = [
            {"step_index": 0, "title": "Decompose objective & gather system/memory context", "assigned_agent": "master_planning_agent", "depends_on": []},
            {"step_index": 1, "title": "Monitor resource health & execute core reasoning", "assigned_agent": "system_monitoring_agent", "depends_on": [0]},
            {"step_index": 2, "title": "Verify task output completeness", "assigned_agent": "qa_agent", "depends_on": [1]},
        ]
        return category, complexity, steps

    def create_task(
        self,
        objective: str,
        priority: int = 5,
        mode_used: str = "offline",
        max_retries: int = 2,
        custom_steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        # Transition Pending -> Planning while decomposing
        category, complexity, generated_steps = self.classify_and_decompose(objective)
        steps = custom_steps if custom_steps is not None else generated_steps

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO tasks
                (id, objective, category, priority, complexity, state, mode_used, plan_json,
                 checkpoint_json, result_summary, verified, retry_count, max_retries, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'Pending', ?, ?, '{}', '', 0, 0, ?, ?, ?)
                """,
                (
                    task_id,
                    objective.strip(),
                    category,
                    max(1, min(10, int(priority))),
                    complexity,
                    mode_used,
                    json.dumps(steps),
                    max(0, min(5, int(max_retries))),
                    now,
                    now,
                ),
            )
            for s in steps:
                sub_id = f"{task_id}_s{s['step_index']}"
                conn.execute(
                    """
                    INSERT INTO subtasks
                    (id, task_id, step_index, title, assigned_agent, depends_on_json, state, output_json, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, 'Pending', '{}', 0)
                    """,
                    (
                        sub_id,
                        task_id,
                        int(s["step_index"]),
                        s["title"],
                        s["assigned_agent"],
                        json.dumps(s.get("depends_on", [])),
                    ),
                )

        self.audit.log_event(
            event_type="task_created",
            actor="master_planner",
            category=category,
            decision="planned",
            details=f"Created task {task_id} ({len(steps)} subtasks): {objective[:100]}",
        )
        return self.get_task(task_id)  # type: ignore[return-value]

    def update_task_state(
        self,
        task_id: str,
        new_state: str,
        result_summary: str | None = None,
        verified: bool | None = None,
        error_message: str | None = None,
        checkpoint: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if new_state not in TASK_STATES:
            raise ValueError(f"Invalid task state '{new_state}'")
        if new_state == "Completed" and not verified:
            raise ValueError("Task cannot enter 'Completed' state without passing verification (verified=True).")

        existing = self.get_task(task_id)
        if not existing:
            raise KeyError(f"Task not found: {task_id}")

        now = datetime.now(timezone.utc).isoformat()
        completed_at = now if new_state in {"Completed", "Failed", "Cancelled"} else existing.get("completed_at")
        merged_checkpoint = dict(existing.get("checkpoint", {}))
        if checkpoint:
            merged_checkpoint.update(checkpoint)

        self.db.execute(
            """
            UPDATE tasks
            SET state = ?,
                result_summary = COALESCE(?, result_summary),
                verified = COALESCE(?, verified),
                error_message = ?,
                checkpoint_json = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                new_state,
                result_summary,
                (1 if verified else 0) if verified is not None else None,
                error_message,
                json.dumps(merged_checkpoint, default=str),
                now,
                completed_at,
                task_id,
            ),
        )
        return self.get_task(task_id)  # type: ignore[return-value]

    def update_subtask(
        self,
        subtask_id: str,
        state: str,
        output: dict[str, Any] | None = None,
        error_message: str | None = None,
        increment_retry: bool = False,
    ) -> None:
        if state not in TASK_STATES:
            raise ValueError(f"Invalid subtask state '{state}'")
        now = datetime.now(timezone.utc).isoformat()
        started_col = now if state == "Running" else None
        done_col = now if state in {"Completed", "Failed", "Cancelled"} else None

        self.db.execute(
            """
            UPDATE subtasks
            SET state = ?,
                output_json = COALESCE(?, output_json),
                error_message = ?,
                retry_count = retry_count + ?,
                started_at = COALESCE(started_at, ?),
                completed_at = COALESCE(?, completed_at)
            WHERE id = ?
            """,
            (
                state,
                json.dumps(output, default=str) if output is not None else None,
                error_message,
                1 if increment_retry else 0,
                started_col,
                done_col,
                subtask_id,
            ),
        )

    def cancel_task(self, task_id: str, reason: str = "Cancelled by user") -> dict[str, Any]:
        self.db.execute(
            "UPDATE subtasks SET state = 'Cancelled' WHERE task_id = ? AND state IN ('Pending', 'Planning', 'Running', 'Waiting')",
            (task_id,),
        )
        return self.update_task_state(task_id, "Cancelled", error_message=reason, verified=False)

    def get_resumable_tasks_after_restart(self) -> list[dict[str, Any]]:
        """Identify workflows interrupted mid-flight (Running/Planning/Waiting) so they can resume cleanly."""
        rows = self.db.query_all(
            "SELECT id FROM tasks WHERE state IN ('Running', 'Planning', 'Waiting') ORDER BY priority DESC, created_at ASC"
        )
        resumable: list[dict[str, Any]] = []
        for r in rows:
            # Reset in-flight 'Running' subtasks back to 'Pending' while preserving completed subtasks!
            self.db.execute(
                "UPDATE subtasks SET state = 'Pending' WHERE task_id = ? AND state = 'Running'",
                (r["id"],),
            )
            self.update_task_state(r["id"], "Pending", checkpoint={"recovered_after_restart": True})
            task = self.get_task(r["id"])
            if task:
                resumable.append(task)
        return resumable

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
        if not row:
            return None
        sub_rows = self.db.query_all(
            "SELECT * FROM subtasks WHERE task_id = ? ORDER BY step_index ASC",
            (task_id,),
        )
        subtasks = [
            {
                "id": s["id"],
                "step_index": s["step_index"],
                "title": s["title"],
                "assigned_agent": s["assigned_agent"],
                "depends_on": json.loads(s["depends_on_json"] or "[]"),
                "state": s["state"],
                "output": json.loads(s["output_json"] or "{}"),
                "error_message": s["error_message"],
                "retry_count": s["retry_count"],
                "started_at": s["started_at"],
                "completed_at": s["completed_at"],
            }
            for s in sub_rows
        ]
        return {
            "id": row["id"],
            "objective": row["objective"],
            "category": row["category"],
            "priority": row["priority"],
            "complexity": row["complexity"],
            "state": row["state"],
            "mode_used": row["mode_used"],
            "plan": json.loads(row["plan_json"] or "[]"),
            "checkpoint": json.loads(row["checkpoint_json"] or "{}"),
            "result_summary": row["result_summary"],
            "verified": bool(row["verified"]),
            "error_message": row["error_message"],
            "retry_count": row["retry_count"],
            "max_retries": row["max_retries"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "subtasks": subtasks,
        }

    def list_tasks(self, state: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if state:
            rows = self.db.query_all(
                "SELECT id FROM tasks WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state, limit),
            )
        else:
            rows = self.db.query_all("SELECT id FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
        return [t for r in rows if (t := self.get_task(r["id"])) is not None]
