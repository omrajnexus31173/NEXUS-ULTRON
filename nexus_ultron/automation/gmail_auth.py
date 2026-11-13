"""Authorized Gmail OAuth2 & Secure OTP Authentication Intelligence (Zero Log/Prompt Exposure)."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from ..core.logging_engine import register_ephemeral_secret
from ..security.audit_logger import AuditLogger
from ..security.credential_vault import CredentialVault
from ..security.payment_isolation import PaymentIsolationEngine, PaymentIsolationTriggered
from ..security.permission_engine import PermissionEngine
from ..security.prompt_guard import PromptInjectionShield

logger = logging.getLogger("nexus_ultron.gmail_auth")

GMAIL_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"

_OTP_REGEX = re.compile(
    r"(?i)(?:verification\s+code|login\s+code|security\s+code|one[- ]time\s+passcode|otp)\s*(?:is|:|-)?\s*\b(\d{6,8})\b"
)
_PAYMENT_OTP_MARKER = re.compile(
    r"(?i)\b(transaction\s+otp|payment\s+otp|debit\s+of|credit\s+card|netbanking|upi\s+transaction|3d\s*secure)\b"
)
_MOBILE_SMS_ONLY_MARKER = re.compile(
    r"(?i)\b(sent\s+to\s+your\s+mobile|sms\s+verification\s+sent|approve\s+on\s+your\s+phone|authenticator\s+app)\b"
)
_CAPTCHA_MFA_MARKER = re.compile(r"(?i)\b(captcha|security\s+key|hardware\s+token|biometric)\b")


@dataclass
class ActiveAuthSession:
    session_id: str
    service_domain: str
    account_hint: str
    started_at: datetime
    status: str = "awaiting_verification"
    human_action_required: str | None = None


class GmailAuthEngine:
    """
    Implements secure OAuth2 Gmail message access and explicit-opt-in login OTP matching:
      - Never requests or stores raw Gmail passwords
      - Registers extracted OTPs as ephemeral secrets so logs & AI prompts automatically redact them
      - Blocks bank/payment transaction OTPs via Payment Isolation
      - Detects expired OTPs and notifies user when MFA/CAPTCHA/mobile SMS requires human action
    """

    def __init__(
        self,
        vault: CredentialVault,
        permissions: PermissionEngine,
        payment_shield: PaymentIsolationEngine,
        prompt_shield: PromptInjectionShield,
        audit: AuditLogger,
        otp_max_age_seconds: int = 300,
    ) -> None:
        self.vault = vault
        self.permissions = permissions
        self.payment_shield = payment_shield
        self.prompt_shield = prompt_shield
        self.audit = audit
        self.otp_max_age_seconds = otp_max_age_seconds
        self._active_sessions: dict[str, ActiveAuthSession] = {}
        self._test_messages: list[dict[str, Any]] = []
        self._http_transport: httpx.BaseTransport | None = None

    def set_http_transport(self, transport: httpx.BaseTransport | None) -> None:
        self._http_transport = transport

    def inject_test_messages(self, messages: list[dict[str, Any]]) -> None:
        """QA hook allowing safe simulated verification emails using test accounts (never real financial accounts)."""
        self._test_messages = list(messages)

    def build_oauth2_pkce_authorization_url(
        self,
        client_id: str,
        redirect_uri: str = "http://127.0.0.1:8765/oauth2/callback",
    ) -> dict[str, str]:
        """Create a standards-compliant Google OAuth2 Authorization Code + PKCE URL (no raw password)."""
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode("ascii")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .rstrip(b"=")
            .decode("ascii")
        )
        state = base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode("ascii")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
            "access_type": "offline",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
            "prompt": "consent",
        }
        return {
            "authorization_url": f"{GMAIL_AUTH_URL}?{urlencode(params)}",
            "code_verifier": verifier,
            "state": state,
        }

    def start_auth_session(self, session_id: str, service_domain: str, account_hint: str = "") -> ActiveAuthSession:
        self.payment_shield.assert_safe_for_browser(f"https://{service_domain}")
        sess = ActiveAuthSession(
            session_id=session_id,
            service_domain=service_domain.lower(),
            account_hint=account_hint.lower(),
            started_at=datetime.now(timezone.utc),
        )
        self._active_sessions[session_id] = sess
        return sess

    def search_messages(self, query: str = "", max_results: int = 10) -> list[dict[str, Any]]:
        """Read authorized email metadata & sanitized bodies without exposing OTPs."""
        self.permissions.require_permission(
            "authorized_email_reading",
            actor="email_agent",
            action_desc=f"search_messages '{query}'",
        )
        raw_msgs = self._fetch_raw_messages(query=query, max_results=max_results)
        sanitized_list: list[dict[str, Any]] = []
        for m in raw_msgs:
            body = str(m.get("body", ""))
            # Register any OTP in body immediately so it can never leak into logs or LLM prompts!
            otp_hit = _OTP_REGEX.search(body)
            if otp_hit:
                register_ephemeral_secret(otp_hit.group(1))
            shielded = self.prompt_shield.inspect_and_wrap(
                _OTP_REGEX.sub("verification code: [PROTECTED_OTP]", body),
                source=f"email:{m.get('sender', 'unknown')}",
            )
            sanitized_list.append(
                {
                    "id": m.get("id"),
                    "sender": m.get("sender", ""),
                    "subject": m.get("subject", ""),
                    "received_at": m.get("received_at"),
                    "sanitized_body": shielded.safe_text,
                }
            )
        return sanitized_list

    def match_and_apply_login_otp(
        self,
        session_id: str,
        target_field_callback: Any | None = None,
    ) -> dict[str, Any]:
        """
        Match an OTP strictly to the corresponding active non-financial authentication session,
        validate expiration, detect mobile/MFA/CAPTCHA handoffs, and inject directly into the
        authorized login callback without ever returning raw OTPs to logs or unrelated agents!
        """
        self.permissions.require_permission("authorized_email_reading", actor="email_agent", action_desc="read verification email")
        self.permissions.require_permission("otp_retrieval", actor="email_agent", action_desc=f"otp match for {session_id}")

        session = self._active_sessions.get(session_id)
        if not session:
            raise KeyError(f"Unknown authentication session '{session_id}'")

        # Ensure target domain is never a banking/payment domain
        self.payment_shield.assert_safe_for_browser(f"https://{session.service_domain}")

        messages = self._fetch_raw_messages(query=session.service_domain, max_results=20)
        now = datetime.now(timezone.utc)
        found_expired = False

        for msg in messages:
            sender = str(msg.get("sender", "")).lower()
            subject = str(msg.get("subject", ""))
            body = str(msg.get("body", ""))
            combined = f"{sender}\n{subject}\n{body}"

            # 1. Never touch banking / 3DS / UPI / payment transaction OTPs!
            if _PAYMENT_OTP_MARKER.search(combined):
                self.audit.log_event(
                    event_type="payment_otp_ignored",
                    actor="email_agent",
                    category="payment_isolation",
                    decision="blocked",
                    details="Skipped financial/transaction OTP email.",
                )
                if session.service_domain in sender:
                    raise PaymentIsolationTriggered("Refusing to read financial/payment OTP.")
                continue

            # 2. Match strictly to the active login session's service domain
            if session.service_domain not in sender and session.service_domain not in combined.lower():
                continue

            # 3. Check if MFA / CAPTCHA / Mobile SMS requires human intervention
            if _MOBILE_SMS_ONLY_MARKER.search(combined) or _CAPTCHA_MFA_MARKER.search(combined):
                session.status = "waiting_user_intervention"
                session.human_action_required = (
                    "Verification requires mobile device / authenticator / CAPTCHA approval inaccessible to ULTRON. "
                    "Please complete this verification step directly."
                )
                return {
                    "session_id": session_id,
                    "status": "user_intervention_required",
                    "message": session.human_action_required,
                    "otp_applied": False,
                }

            otp_match = _OTP_REGEX.search(combined)
            if not otp_match:
                continue

            otp_code = otp_match.group(1)
            # Register immediately so LoggingEngine & AIProviderRouter scrub it everywhere!
            register_ephemeral_secret(otp_code)

            received_raw = msg.get("received_at")
            received_dt = (
                datetime.fromisoformat(received_raw)
                if isinstance(received_raw, str)
                else now
            )
            if received_dt.tzinfo is None:
                received_dt = received_dt.replace(tzinfo=timezone.utc)

            age_sec = (now - received_dt).total_seconds()
            if age_sec > self.otp_max_age_seconds:
                found_expired = True
                continue

            # Deliver directly into the authorized session callback without returning raw OTP in logs/summaries
            if callable(target_field_callback):
                target_field_callback(otp_code)

            session.status = "authenticated"
            self.audit.log_event(
                event_type="login_otp_applied",
                actor="email_agent",
                category="otp_authentication",
                decision="allowed",
                details=f"Matched valid verification code for authorized session '{session_id}' ({session.service_domain})",
            )
            return {
                "session_id": session_id,
                "service_domain": session.service_domain,
                "status": "authenticated",
                "otp_applied": True,
                "expired": False,
            }

        if found_expired:
            session.status = "otp_expired"
            return {
                "session_id": session_id,
                "status": "expired_code_detected",
                "otp_applied": False,
                "expired": True,
                "message": "Found matching verification code, but it has expired. Request a fresh code.",
            }

        return {
            "session_id": session_id,
            "status": "awaiting_verification_email",
            "otp_applied": False,
            "expired": False,
            "message": "No matching verification email arrived yet; if sent to mobile SMS, user assistance is needed.",
        }

    def _fetch_raw_messages(self, query: str = "", max_results: int = 10) -> list[dict[str, Any]]:
        if self._test_messages:
            if not query:
                return self._test_messages[:max_results]
            q = query.lower()
            return [
                m
                for m in self._test_messages
                if q in str(m.get("sender", "")).lower()
                or q in str(m.get("subject", "")).lower()
                or q in str(m.get("body", "")).lower()
            ][:max_results]

        token = self.vault.get_secret("GMAIL_OAUTH_ACCESS_TOKEN")
        if not token:
            return []

        with httpx.Client(timeout=15.0, transport=self._http_transport) as client:
            resp = client.get(
                GMAIL_MESSAGES_URL,
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "maxResults": max_results},
            )
            resp.raise_for_status()
            listing = resp.json().get("messages", [])
            results: list[dict[str, Any]] = []
            for item in listing[:max_results]:
                detail = client.get(
                    f"{GMAIL_MESSAGES_URL}/{item['id']}",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"format": "full"},
                ).json()
                headers = {
                    h["name"].lower(): h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }
                snippet = detail.get("snippet", "")
                results.append(
                    {
                        "id": item["id"],
                        "sender": headers.get("from", ""),
                        "subject": headers.get("subject", ""),
                        "body": snippet,
                        "received_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            return results
