"""Persistent Local Memory & Knowledge System (FTS5 + Local Semantic Vectors + Sensitive Guard)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.logging_engine import redact_sensitive_text
from .database import DatabaseManager

VALID_NAMESPACES = {"temporary", "long_term", "project", "instruction", "knowledge"}

# Patterns that must NEVER be silently stored in memory
_SENSITIVE_MEMORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "API key token"),
    (re.compile(r"(?i)\b(password|passwd|private[_ ]?key|client[_ ]?secret)\s*[:=]\s*\S+"), "credential/password"),
    (re.compile(r"\b(?:\d[ -]*?){15,19}\b"), "payment card number"),
    (re.compile(r"(?i)\b(cvv|cvc|upi\s*pin|netbanking\s*password)\s*[:=]?\s*\d{3,6}\b"), "financial PIN/CVV"),
    (re.compile(r"(?i)\b(otp|verification\s+code)\s*(?:is|:|=)\s*\d{4,8}\b"), "authentication OTP"),
]


class SensitiveMemoryError(ValueError):
    """Raised when an attempt is made to persist credentials, payment data, or OTPs into memory."""


def _compute_local_semantic_embedding(text: str, dims: int = 64) -> list[float]:
    """
    Lightweight, zero-GPU deterministic hashed n-gram vector embedding for offline semantic search.
    Runs in <1ms on 8 GB RAM laptops with zero external model overhead.
    """
    vec = [0.0] * dims
    tokens = re.findall(r"[a-z0-9_]{2,}", (text or "").lower())
    if not tokens:
        return vec
    features = list(tokens) + [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dims
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [round(v / norm, 5) for v in vec]
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class MemorySystem:
    """
    Manages separated Temporary, Long-Term, Project, Saved Instruction, and Knowledge memory,
    plus Conversations, User Preferences, and Notes/Reminders.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    @staticmethod
    def assert_not_sensitive(text: str) -> None:
        for pattern, reason in _SENSITIVE_MEMORY_PATTERNS:
            if pattern.search(text or ""):
                raise SensitiveMemoryError(
                    f"Refusing to store sensitive {reason} in memory. Use the encrypted Credential Vault instead."
                )

    # --- Preferences ---
    def set_preference(self, key: str, value: Any) -> None:
        self.assert_not_sensitive(f"{key}={value}")
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO preferences (pref_key, pref_value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(pref_key) DO UPDATE SET pref_value=excluded.pref_value, updated_at=excluded.updated_at
            """,
            (key, json.dumps(value), now),
        )

    def get_preference(self, key: str, default: Any = None) -> Any:
        row = self.db.query_one("SELECT pref_value FROM preferences WHERE pref_key = ?", (key,))
        if not row:
            return default
        try:
            return json.loads(row["pref_value"])
        except Exception:
            return row["pref_value"]

    def list_preferences(self) -> dict[str, Any]:
        rows = self.db.query_all("SELECT pref_key, pref_value FROM preferences ORDER BY pref_key")
        out: dict[str, Any] = {}
        for r in rows:
            try:
                out[r["pref_key"]] = json.loads(r["pref_value"])
            except Exception:
                out[r["pref_key"]] = r["pref_value"]
        return out

    # --- Memory CRUD & Hybrid FTS5 + Semantic Search ---
    def add_memory(
        self,
        title: str,
        content: str,
        namespace: str = "long_term",
        project_id: str | None = None,
        tags: list[str] | None = None,
        importance: int = 5,
    ) -> dict[str, Any]:
        if namespace not in VALID_NAMESPACES:
            raise ValueError(f"Invalid memory namespace '{namespace}'. Expected one of {sorted(VALID_NAMESPACES)}")
        self.assert_not_sensitive(f"{title}\n{content}")

        entry_id = f"mem_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        tags_list = [str(t).strip() for t in (tags or []) if str(t).strip()]
        embedding = _compute_local_semantic_embedding(f"{title} {content} {' '.join(tags_list)}")

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries
                (id, namespace, project_id, title, content, tags_json, embedding_json, importance, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    namespace,
                    project_id,
                    title.strip(),
                    content.strip(),
                    json.dumps(tags_list),
                    json.dumps(embedding),
                    max(1, min(10, int(importance))),
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO memory_fts (entry_id, title, content, tags) VALUES (?, ?, ?, ?)",
                (entry_id, title.strip(), content.strip(), " ".join(tags_list)),
            )
        return self.get_memory(entry_id)  # type: ignore[return-value]

    def get_memory(self, entry_id: str) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM memory_entries WHERE id = ?", (entry_id,))
        return self._format_memory_row(row) if row else None

    def update_memory(
        self,
        entry_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
        namespace: str | None = None,
    ) -> dict[str, Any]:
        existing = self.get_memory(entry_id)
        if not existing:
            raise KeyError(f"Memory entry not found: {entry_id}")
        new_title = title.strip() if title is not None else existing["title"]
        new_content = content.strip() if content is not None else existing["content"]
        new_ns = namespace if namespace is not None else existing["namespace"]
        if new_ns not in VALID_NAMESPACES:
            raise ValueError(f"Invalid namespace: {new_ns}")
        self.assert_not_sensitive(f"{new_title}\n{new_content}")
        new_tags = tags if tags is not None else existing["tags"]
        embedding = _compute_local_semantic_embedding(f"{new_title} {new_content} {' '.join(new_tags)}")
        now = datetime.now(timezone.utc).isoformat()

        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE memory_entries
                SET title = ?, content = ?, namespace = ?, tags_json = ?, embedding_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_title, new_content, new_ns, json.dumps(new_tags), json.dumps(embedding), now, entry_id),
            )
            conn.execute("DELETE FROM memory_fts WHERE entry_id = ?", (entry_id,))
            conn.execute(
                "INSERT INTO memory_fts (entry_id, title, content, tags) VALUES (?, ?, ?, ?)",
                (entry_id, new_title, new_content, " ".join(new_tags)),
            )
        return self.get_memory(entry_id)  # type: ignore[return-value]

    def delete_memory(self, entry_id: str) -> bool:
        with self.db.connection() as conn:
            cur = conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
            conn.execute("DELETE FROM memory_fts WHERE entry_id = ?", (entry_id,))
            return cur.rowcount > 0

    def list_memories(
        self,
        namespace: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = self.db.query_all(
            f"SELECT * FROM memory_entries {where} ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        )
        return [self._format_memory_row(r) for r in rows]

    def search_memory(
        self,
        query: str,
        namespace: str | None = None,
        project_id: str | None = None,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining SQLite FTS5 keyword rank and local semantic cosine similarity."""
        cleaned_tokens = re.findall(r"[a-zA-Z0-9_]+", query or "")
        if not cleaned_tokens:
            return self.list_memories(namespace=namespace, project_id=project_id, limit=limit)

        fts_query = " OR ".join(f'"{tok}"*' for tok in cleaned_tokens[:8])
        fts_hits: dict[str, float] = {}
        try:
            fts_rows = self.db.query_all(
                "SELECT entry_id, bm25(memory_fts) AS rank_score FROM memory_fts WHERE memory_fts MATCH ? LIMIT 50",
                (fts_query,),
            )
            for idx, r in enumerate(fts_rows):
                fts_hits[r["entry_id"]] = 1.0 / (1.0 + idx)
        except Exception:
            pass

        candidates = self.list_memories(namespace=namespace, project_id=project_id, limit=250)
        q_vec = _compute_local_semantic_embedding(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for entry in candidates:
            entry_row = self.db.query_one("SELECT embedding_json FROM memory_entries WHERE id = ?", (entry["id"],))
            emb = json.loads(entry_row["embedding_json"]) if entry_row and entry_row["embedding_json"] else []
            sem_score = max(0.0, _cosine_similarity(q_vec, emb))
            kw_score = fts_hits.get(entry["id"], 0.0)
            total = round(0.65 * kw_score + 0.35 * sem_score, 4)
            if total > 0.02 or any(tok.lower() in (entry["title"] + " " + entry["content"]).lower() for tok in cleaned_tokens):
                enriched = dict(entry)
                enriched["relevance_score"] = max(total, 0.1)
                scored.append((enriched["relevance_score"], enriched))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # --- Conversations & Messages ---
    def create_conversation(self, title: str = "New Session", mode_used: str = "offline") -> dict[str, Any]:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO conversations (id, title, mode_used, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, title.strip() or "New Session", mode_used, now, now),
        )
        return {"id": conv_id, "title": title, "mode_used": mode_used, "created_at": now, "updated_at": now}

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        provider: str = "ultron_local_core",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        safe_content = redact_sensitive_text(content)
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        with self.db.connection() as conn:
            exists = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO conversations (id, title, mode_used, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (conversation_id, safe_content[:48] or "Conversation", "offline", now, now),
                )
            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, provider, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (msg_id, conversation_id, role, safe_content, provider, json.dumps(metadata or {}), now),
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": safe_content,
            "provider": provider,
            "created_at": now,
        }

    def get_conversation_messages(self, conversation_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC LIMIT ?",
            (conversation_id, limit),
        )

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        )

    # --- Notes & Reminders (Offline Productivity) ---
    def add_note_or_reminder(
        self,
        title: str,
        body: str,
        item_type: str = "note",
        due_at: str | None = None,
    ) -> dict[str, Any]:
        if item_type not in {"note", "reminder"}:
            raise ValueError("item_type must be 'note' or 'reminder'")
        self.assert_not_sensitive(f"{title}\n{body}")
        item_id = f"{item_type}_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO notes_reminders (id, item_type, title, body, due_at, completed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (item_id, item_type, title.strip(), body.strip(), due_at, now, now),
        )
        return self.db.query_one("SELECT * FROM notes_reminders WHERE id = ?", (item_id,))  # type: ignore[return-value]

    def list_notes_reminders(self, item_type: str | None = None) -> list[dict[str, Any]]:
        if item_type:
            return self.db.query_all(
                "SELECT * FROM notes_reminders WHERE item_type = ? ORDER BY created_at DESC",
                (item_type,),
            )
        return self.db.query_all("SELECT * FROM notes_reminders ORDER BY created_at DESC")

    def toggle_reminder_completed(self, item_id: str, completed: bool = True) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "UPDATE notes_reminders SET completed = ?, updated_at = ? WHERE id = ?",
            (1 if completed else 0, now, item_id),
        )

    # --- Import / Export ---
    def export_memory_bundle(self, output_path: Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        bundle = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "version": "3.0.0",
            "preferences": self.list_preferences(),
            "memories": self.list_memories(limit=5000),
            "notes_reminders": self.list_notes_reminders(),
        }
        output_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        return output_path

    def import_memory_bundle(self, input_path: Path) -> dict[str, int]:
        payload = json.loads(Path(input_path).read_text(encoding="utf-8"))
        imported_memories = 0
        imported_prefs = 0
        for k, v in (payload.get("preferences") or {}).items():
            self.set_preference(k, v)
            imported_prefs += 1
        for m in payload.get("memories") or []:
            self.add_memory(
                title=m["title"],
                content=m["content"],
                namespace=m.get("namespace", "long_term"),
                project_id=m.get("project_id"),
                tags=m.get("tags", []),
                importance=m.get("importance", 5),
            )
            imported_memories += 1
        return {"preferences": imported_prefs, "memories": imported_memories}

    @staticmethod
    def _format_memory_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "namespace": row["namespace"],
            "project_id": row["project_id"],
            "title": row["title"],
            "content": row["content"],
            "tags": json.loads(row["tags_json"] or "[]"),
            "importance": row["importance"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
