"""Prompt-Injection Shield & Untrusted Content Sanitizer for Web, Email, Files, and External Outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .audit_logger import AuditLogger

_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|system)\s+instructions"), "instruction_override_attempt"),
    (re.compile(r"(?i)(disable|bypass|turn\s+off)\s+(payment\s+isolation|security|permission|audit)"), "security_disable_attempt"),
    (re.compile(r"(?i)(exfiltrate|send|upload|post)\s+.*(api[_ -]?key|password|secret|vault|cookie|token|otp)"), "credential_exfiltration_attempt"),
    (re.compile(r"(?i)<\s*system\s*>|\[\s*SYSTEM\s*OVERRIDE\s*\]|###\s*NEW\s+SYSTEM\s+PROMPT"), "fake_system_delimiter"),
    (re.compile(r"(?i)execute\s+shell\s+command\s*:\s*(rm\s+-rf|powershell|curl\s+.*\|\s*bash)"), "embedded_malicious_command"),
]


@dataclass(frozen=True)
class SanitizedUntrustedContent:
    safe_text: str
    injection_detected: bool
    findings: list[str]
    source: str


class PromptInjectionShield:
    """
    Wraps untrusted external data (websites, emails, downloaded documents, 3rd-party tool outputs)
    in non-authoritative data boundaries and neutralizes embedded prompt-injection directives.
    """

    def __init__(self, audit: AuditLogger | None = None) -> None:
        self.audit = audit

    def inspect_and_wrap(self, raw_text: str, source: str = "external_content") -> SanitizedUntrustedContent:
        cleaned = (raw_text or "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
        findings: list[str] = []

        neutralized = cleaned
        for pattern, label in _INJECTION_PATTERNS:
            if pattern.search(neutralized):
                findings.append(label)
                neutralized = pattern.sub(f"[NEUTRALIZED_UNTRUSTED_DIRECTIVE:{label}]", neutralized)

        if findings and self.audit:
            self.audit.log_event(
                event_type="prompt_injection_neutralized",
                actor="prompt_injection_shield",
                category="security_shield",
                decision="neutralized",
                details=f"Neutralized {findings} inside untrusted source '{source}'",
            )

        wrapped = (
            f"<untrusted_data source=\"{source}\" authority=\"none\">\n"
            f"{neutralized}\n"
            f"</untrusted_data>"
        )
        return SanitizedUntrustedContent(
            safe_text=wrapped,
            injection_detected=bool(findings),
            findings=findings,
            source=source,
        )
