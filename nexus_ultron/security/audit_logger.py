"""Tamper-evident hash-chained security and permission audit logger."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from ..core.logging_engine import redact_sensitive_text
from ..storage.database import DatabaseManager


class AuditLogger:
    """Records security, permission, automation, and isolation decisions with SHA-256 hash chaining."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def log_event(
        self,
        event_type: str,
        actor: str,
        category: str,
        decision: str,
        details: str,
    ) -> dict[str, Any]:
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        redacted_details = redact_sensitive_text(details)

        with self.db.connection() as conn:
            last = conn.execute(
                "SELECT entry_hash FROM security_audit_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = last["entry_hash"] if last else ("0" * 64)
            payload = f"{event_id}|{event_type}|{actor}|{category}|{decision}|{redacted_details}|{prev_hash}|{now}"
            entry_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

            conn.execute(
                """
                INSERT INTO security_audit_log
                (event_id, event_type, actor, category, decision, details_redacted, prev_hash, entry_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, event_type, actor, category, decision, redacted_details, prev_hash, entry_hash, now),
            )
        return {
            "event_id": event_id,
            "event_type": event_type,
            "actor": actor,
            "category": category,
            "decision": decision,
            "details": redacted_details,
            "entry_hash": entry_hash,
            "created_at": now,
        }

    def list_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM security_audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        )

    def verify_integrity(self) -> tuple[bool, int]:
        """Verify the cryptographic hash chain across all audit entries."""
        rows = self.db.query_all("SELECT * FROM security_audit_log ORDER BY id ASC")
        expected_prev = "0" * 64
        for row in rows:
            if row["prev_hash"] != expected_prev:
                return False, int(row["id"])
            payload = (
                f"{row['event_id']}|{row['event_type']}|{row['actor']}|{row['category']}|"
                f"{row['decision']}|{row['details_redacted']}|{row['prev_hash']}|{row['created_at']}"
            )
            computed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if computed != row["entry_hash"]:
                return False, int(row["id"])
            expected_prev = computed
        return True, len(rows)
