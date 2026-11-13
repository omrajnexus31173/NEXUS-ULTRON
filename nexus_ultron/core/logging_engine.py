"""Centralized structured logging, secret/OTP redaction, and crash diagnostics."""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import threading
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Patterns that must NEVER appear in logs, crash dumps, or external prompts
_REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # OpenAI / Anthropic / API keys / Bearer tokens
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|passwd|access[_-]?token|refresh[_-]?token)\s*[:=]\s*['\"]?([^\s,'\";]+)"), r"\1=[REDACTED_SECRET]"),
    # Explicit OTP markers and standalone 6-8 digit verification codes near OTP context
    (re.compile(r"(?i)(otp|verification\s+code|security\s+code|passcode|login\s+code)\s*(?:is|:|=)?\s*['\"]?\b(\d{4,8})\b"), r"\1: [REDACTED_OTP]"),
    # Payment card numbers (13-19 digits with optional spaces/dashes)
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[REDACTED_PAYMENT_NUMBER]"),
    # CVV patterns
    (re.compile(r"(?i)\b(cvv|cvc|csc)\s*[:=]?\s*\d{3,4}\b"), r"\1=[REDACTED_CVV]"),
]

_DYNAMIC_SENSITIVE_VALUES: set[str] = set()
_SENSITIVE_LOCK = threading.Lock()


def register_ephemeral_secret(secret_value: str) -> None:
    """Register an ephemeral secret (e.g., an active OTP or token) for guaranteed log/prompt scrubbing."""
    cleaned = (secret_value or "").strip()
    if len(cleaned) >= 4:
        with _SENSITIVE_LOCK:
            _DYNAMIC_SENSITIVE_VALUES.add(cleaned)


def redact_sensitive_text(text: str) -> str:
    """Scrub API keys, passwords, OAuth tokens, OTPs, and card numbers from text."""
    if not text:
        return text
    result = str(text)
    with _SENSITIVE_LOCK:
        ephemerals = list(_DYNAMIC_SENSITIVE_VALUES)
    for val in ephemerals:
        if val in result:
            result = result.replace(val, "[REDACTED_EPHEMERAL_SECRET]")
    for pattern, replacement in _REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class SecretRedactionFilter(logging.Filter):
    """Logging filter ensuring sensitive values never reach disk or UI buffers."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            try:
                formatted = record.getMessage()
                record.msg = redact_sensitive_text(formatted)
                record.args = ()
            except Exception:
                record.msg = redact_sensitive_text(str(record.msg))
                record.args = ()
        else:
            record.msg = redact_sensitive_text(str(record.msg))
        return True


class RingBufferHandler(logging.Handler):
    """Thread-safe in-memory log buffer for live dashboard display."""

    def __init__(self, capacity: int = 500) -> None:
        super().__init__()
        self._records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(self.format(record)),
        }
        with self._lock:
            self._records.append(entry)

    def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._records)
        return items[-limit:]


class LoggingEngine:
    """Centralized logging and crash-reporting facility."""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.crash_dir = self.log_dir / "crash_reports"
        self.crash_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "nexus_ultron.log"
        self.ring_handler = RingBufferHandler(capacity=600)
        self._configured = False
        self._configure()

    def _configure(self) -> None:
        root_logger = logging.getLogger("nexus_ultron")
        root_logger.setLevel(logging.INFO)
        # Close and remove existing handlers to release file handles
        # (critical on Windows where open file handles block deletion)
        for handler in list(root_logger.handlers):
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
        root_logger.handlers.clear()

        redactor = SecretRedactionFilter()
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)

        self.ring_handler.setFormatter(logging.Formatter("%(message)s"))
        self.ring_handler.addFilter(redactor)

        root_logger.addHandler(file_handler)
        root_logger.addHandler(self.ring_handler)
        root_logger.propagate = False
        self._configured = True

    def get_logger(self, component: str) -> logging.Logger:
        return logging.getLogger(f"nexus_ultron.{component}")

    def recent_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.ring_handler.get_recent(limit=limit)

    def record_crash_report(self, subsystem: str, exc: BaseException, context: dict[str, Any] | None = None) -> Path:
        """Write a redacted diagnostic crash report."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = self.crash_dir / f"crash_{subsystem}_{ts}.json"
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "subsystem": subsystem,
            "error_type": type(exc).__name__,
            "error_message": redact_sensitive_text(str(exc)),
            "traceback": redact_sensitive_text(tb_str),
            "context": json.loads(redact_sensitive_text(json.dumps(context or {}, default=str))),
        }
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.get_logger("crash_reporter").error(
            "Crash captured in subsystem '%s': %s (report: %s)",
            subsystem,
            exc,
            report_path.name,
        )
        return report_path
