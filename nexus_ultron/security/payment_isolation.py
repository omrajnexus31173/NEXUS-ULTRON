"""Dedicated Multi-Layer Payment & Financial Isolation Engine (Mandatory Fail-Closed Boundary)."""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from ..storage.database import DatabaseManager
from .audit_logger import AuditLogger

logger = logging.getLogger("nexus_ultron.payment_isolation")


class PaymentIsolationTriggered(PermissionError):
    """Raised whenever ULTRON detects or suspects a payment, checkout, banking, or money-transfer workflow."""


# Layer 1: Known banking, payment gateway, wallet, UPI, and checkout hostnames/schemes
PROTECTED_SCHEMES = {"upi", "paytmmp", "phonepe", "tez", "gpay", "bhim", "bitcoin", "ethereum"}

PROTECTED_HOST_KEYWORDS = (
    "stripe.com",
    "checkout.stripe.com",
    "paypal.com",
    "razorpay.com",
    "paytm.com",
    "phonepe.com",
    "payu.in",
    "payumoney.com",
    "cashfree.com",
    "ccavenue.com",
    "billdesk.com",
    "instamojo.com",
    "braintreegateway.com",
    "adyen.com",
    "squareupsandbox.com",
    "squareup.com",
    "wise.com",
    "venmo.com",
    "zellepay.com",
    "hdfcbank",
    "icicibank",
    "onlinesbi",
    "sbi.co.in",
    "axisbank",
    "kotak.com",
    "chase.com",
    "bankofamerica",
    "wellsfargo",
    "citibank",
    "hsbc.",
    "barclays.",
    "netbanking",
)

PROTECTED_URL_PATH_PATTERNS = re.compile(
    r"(?i)(/checkout\b|/pay\b|/payment[s]?\b|/billing/pay|/cart/checkout|/upi\b|"
    r"/wire-transfer|/money-transfer|/fund-transfer|/bank-transfer|/order/payment|"
    r"[?&](upi|pa|am|cu|payment_intent|client_secret_pay)=)"
)

# Layer 2: Protected DOM / HTML attributes & financial input fields
PROTECTED_DOM_PATTERNS = re.compile(
    r"(?i)("
    r"autocomplete\s*=\s*['\"]?cc-(number|csc|exp|name|type)|"
    r"name\s*=\s*['\"]?(card[_-]?number|cardnumber|cvv|cvc|csc|expiry|upi[_-]?id|vpa|ifsc|iban|routing[_-]?number|account[_-]?number)|"
    r"id\s*=\s*['\"]?(card[_-]?number|cvv|upi[_-]?pin|netbanking)|"
    r"data-stripe|razorpay-payment-button|paypal-buttons|"
    r"\b(enter\s+upi\s+pin|card\s+verification\s+value|proceed\s+to\s+pay|complete\s+purchase|authorize\s+payment|confirm\s+money\s+transfer)\b"
    r")"
)

# Layer 3: Window title & OS process detection
PROTECTED_WINDOW_PATTERNS = re.compile(
    r"(?i)\b("
    r"checkout|payment\s+gateway|secure\s+payment|netbanking|internet\s+banking|"
    r"upi\s+payment|pay\s+with\s+card|razorpay|stripe\s+checkout|paypal\s+checkout|"
    r"money\s+transfer|fund\s+transfer|wire\s+transfer|wallet\s+transfer|confirm\s+payment"
    r")\b"
)

PROTECTED_PROCESS_NAMES = {
    "paytm.exe",
    "phonepe.exe",
    "gpay.exe",
    "bhim.exe",
    "yono.exe",
}

# Natural-language user/agent instruction guard (refuse to initiate/approve transactions)
PROTECTED_ACTION_INTENT = re.compile(
    r"(?i)\b("
    r"pay\s+(now|bill|invoice|rs|inr|usd|\$)|"
    r"send\s+money|transfer\s+(money|funds|\$\d+|rs\.?\s*\d+)|"
    r"enter\s+(my\s+)?(credit\s+card|debit\s+card|cvv|upi\s+pin)|"
    r"complete\s+(the\s+)?(checkout|purchase|payment)|"
    r"approve\s+(the\s+)?(transaction|payment)|"
    r"buy\s+this\s+item\s+and\s+pay"
    r")\b"
)


@dataclass(frozen=True)
class IsolationVerdict:
    isolated: bool
    source_layer: str
    reason: str
    fail_closed: bool = False


class PaymentIsolationEngine:
    """
    Mandatory security boundary preventing ULTRON from participating in, viewing,
    capturing, inspecting, or automating any payment, checkout, banking, UPI, or money-transfer workflow.
    """

    def __init__(
        self,
        db: DatabaseManager,
        audit: AuditLogger,
        fail_closed_on_uncertainty: bool = True,
    ) -> None:
        self.db = db
        self.audit = audit
        self.fail_closed_on_uncertainty = fail_closed_on_uncertainty
        self._lock = threading.Lock()
        self._active_isolation_lockdown: bool = False
        self._lockdown_reason: str = ""

    @property
    def is_locked_down(self) -> bool:
        with self._lock:
            return self._active_isolation_lockdown

    @property
    def lockdown_reason(self) -> str:
        with self._lock:
            return self._lockdown_reason

    def release_user_completed_payment(self) -> None:
        """Called explicitly by the user once they have independently finished and closed their payment screen."""
        with self._lock:
            self._active_isolation_lockdown = False
            self._lockdown_reason = ""
        self.audit.log_event(
            event_type="payment_isolation_released",
            actor="user",
            category="payment_isolation",
            decision="released",
            details="User manually resumed non-financial ULTRON operation after leaving payment workflow.",
        )

    def inspect_objective(self, objective_text: str) -> IsolationVerdict:
        """Block task instructions asking ULTRON to execute payments or money transfers."""
        if objective_text is None:
            if self.fail_closed_on_uncertainty:
                return self._trigger("intent_guard", "Uncertain/null objective text", "null_objective", fail_closed=True)
            return IsolationVerdict(False, "intent_guard", "ok")

        match = PROTECTED_ACTION_INTENT.search(objective_text)
        if match:
            return self._trigger(
                "intent_guard",
                f"Financial transaction instruction detected ('{match.group(0)}')",
                objective_text[:80],
            )
        return IsolationVerdict(False, "intent_guard", "clear")

    def inspect_url(self, url: str | None) -> IsolationVerdict:
        """Layer 1: Inspect URL scheme, domain, and path before any browser navigation or DOM read."""
        if not url or not isinstance(url, str):
            if self.fail_closed_on_uncertainty:
                return self._trigger("url_guard", "Missing/unreadable URL during navigation check", str(url), fail_closed=True)
            return IsolationVerdict(False, "url_guard", "empty")

        raw = url.strip()
        if raw in {"about:blank", "nexus://home", "nexus://newtab"}:
            return IsolationVerdict(False, "url_guard", "internal_safe_page")

        try:
            parsed = urlparse(raw)
        except Exception:
            return self._trigger("url_guard", "Malformed URL caused uncertain classification", raw[:80], fail_closed=True)

        scheme = (parsed.scheme or "").lower()
        if scheme in PROTECTED_SCHEMES:
            return self._trigger("url_guard", f"Protected payment URI scheme '{scheme}://'", raw[:100])

        host = (parsed.netloc or "").lower()
        for kw in PROTECTED_HOST_KEYWORDS:
            if kw in host:
                return self._trigger("url_guard", f"Protected financial/payment domain '{kw}'", host)

        path_and_query = f"{parsed.path or ''}?{parsed.query or ''}"
        if PROTECTED_URL_PATH_PATTERNS.search(path_and_query):
            return self._trigger("url_guard", "Protected checkout/payment URL path detected", f"{host}{parsed.path}")

        return IsolationVerdict(False, "url_guard", "clear")

    def inspect_dom(self, html_or_dom_snippet: str | None, page_url: str = "") -> IsolationVerdict:
        """Layer 2: Inspect DOM before any agent reads fields or interacts with a web page."""
        url_verdict = self.inspect_url(page_url) if page_url else IsolationVerdict(False, "url_guard", "none")
        if url_verdict.isolated:
            return url_verdict

        if html_or_dom_snippet is None:
            if self.fail_closed_on_uncertainty:
                return self._trigger(
                    "dom_guard",
                    "DOM inspection returned None (uncertain page state — failing closed)",
                    page_url or "unknown_page",
                    fail_closed=True,
                )
            return IsolationVerdict(False, "dom_guard", "empty")

        match = PROTECTED_DOM_PATTERNS.search(html_or_dom_snippet)
        if match:
            return self._trigger(
                "dom_guard",
                f"Protected payment/financial DOM element detected ('{match.group(0)[:40]}')",
                page_url or "dom_inspection",
            )
        return IsolationVerdict(False, "dom_guard", "clear")

    def inspect_window_and_processes(
        self,
        window_titles: list[str] | None,
        process_names: list[str] | None = None,
    ) -> IsolationVerdict:
        """Layer 3 & 4: Inspect active windows/processes before desktop automation or screen capture."""
        if window_titles is None:
            if self.fail_closed_on_uncertainty:
                return self._trigger(
                    "window_screen_guard",
                    "Unable to enumerate active windows prior to screen/UI access — failing closed",
                    "window_enumeration_unavailable",
                    fail_closed=True,
                )
            return IsolationVerdict(False, "window_screen_guard", "none")

        for proc in process_names or []:
            if proc.lower() in PROTECTED_PROCESS_NAMES:
                return self._trigger("process_guard", f"Protected financial app running: {proc}", proc)

        for title in window_titles:
            match = PROTECTED_WINDOW_PATTERNS.search(title or "")
            if match:
                return self._trigger(
                    "window_screen_guard",
                    f"Protected financial/checkout window active ('{match.group(0)}')",
                    title[:80],
                )
        return IsolationVerdict(False, "window_screen_guard", "clear")

    def assert_safe_for_browser(self, url: str, html_content: str = "") -> None:
        v = self.inspect_url(url)
        if v.isolated:
            raise PaymentIsolationTriggered(f"PAYMENT ISOLATION ACTIVE [{v.source_layer}]: {v.reason}")
        if html_content:
            dv = self.inspect_dom(html_content, page_url=url)
            if dv.isolated:
                raise PaymentIsolationTriggered(f"PAYMENT ISOLATION ACTIVE [{dv.source_layer}]: {dv.reason}")

    def assert_safe_for_screen_capture(
        self,
        window_titles: list[str] | None,
        process_names: list[str] | None = None,
    ) -> None:
        v = self.inspect_window_and_processes(window_titles, process_names)
        if v.isolated:
            raise PaymentIsolationTriggered(
                f"SCREEN CAPTURE BLOCKED BY PAYMENT ISOLATION [{v.source_layer}]: {v.reason}"
            )

    def _trigger(
        self,
        source_layer: str,
        reason: str,
        target_descriptor: str,
        fail_closed: bool = False,
    ) -> IsolationVerdict:
        event_id = f"payiso_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        action = (
            "fail_closed_suspended_computer_interaction"
            if fail_closed
            else "automation_halted_dom_and_screen_blocked_user_in_control"
        )
        with self._lock:
            self._active_isolation_lockdown = True
            self._lockdown_reason = f"{source_layer}: {reason}"

        try:
            self.db.execute(
                """
                INSERT INTO payment_isolation_events
                (id, source_layer, trigger_reason, target_descriptor, action_taken, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event_id, source_layer, reason, target_descriptor[:120], action, now),
            )
            self.audit.log_event(
                event_type="payment_isolation_triggered",
                actor="payment_isolation_engine",
                category="payment_isolation",
                decision="blocked",
                details=f"[{source_layer}] {reason} | target={target_descriptor[:80]} | action={action}",
            )
        except Exception as exc:
            logger.error("Failed to record payment isolation event (still enforcing block): %s", exc)

        logger.warning("PAYMENT ISOLATION TRIGGERED [%s]: %s", source_layer, reason)
        return IsolationVerdict(isolated=True, source_layer=source_layer, reason=reason, fail_closed=fail_closed)

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM payment_isolation_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
