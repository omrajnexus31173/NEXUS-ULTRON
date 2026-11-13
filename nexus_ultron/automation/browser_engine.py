"""Dual Browser Intelligence: (A) Isolated ULTRON Chrome Profile & (B) Dedicated NEXUS Browser Engine."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx

from ..security.payment_isolation import PaymentIsolationEngine, PaymentIsolationTriggered
from ..security.permission_engine import PermissionEngine
from ..security.prompt_guard import PromptInjectionShield
from ..storage.database import DatabaseManager

logger = logging.getLogger("nexus_ultron.browser")

CONFIGURED_PLATFORMS: dict[str, str] = {
    "google_search": "https://www.google.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "huggingface": "https://huggingface.co/models",
    "github": "https://github.com",
    "python_docs": "https://docs.python.org/3/",
    "mdn_docs": "https://developer.mozilla.org/",
    "pypi": "https://pypi.org/",
    "gmail": "https://mail.google.com/",
}


def _find_system_chrome_binary() -> str | None:
    if platform.system() == "Windows":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for c in candidates:
            if Path(c).exists():
                return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _get_user_default_chrome_profile_dir() -> Path:
    """Return the OS path of the user's personal Chrome User Data directory (which ULTRON MUST NEVER touch)."""
    if platform.system() == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", r"C:\Users\Default\AppData\Local")
        return Path(local_app) / "Google" / "Chrome" / "User Data"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    return Path.home() / ".config" / "google-chrome"


class BrowserIntelligenceEngine:
    """
    Provides:
      A. Isolated ULTRON-Controlled Google Chrome Profile (never touches, reads, or copies
         the user's existing Chrome profile, bookmarks, cookies, or passwords).
      B. NEXUS Browser state & automation engine (multiple tabs, address bar, search,
         bookmarks, download manager, history, separate profiles, and mandatory Payment Shield).
    """

    def __init__(
        self,
        db: DatabaseManager,
        data_root: Path,
        permissions: PermissionEngine,
        payment_shield: PaymentIsolationEngine,
        prompt_shield: PromptInjectionShield,
    ) -> None:
        self.db = db
        self.data_root = Path(data_root)
        self.permissions = permissions
        self.payment_shield = payment_shield
        self.prompt_shield = prompt_shield

        self.ultron_chrome_profile = (self.data_root / "browser_profiles" / "ultron_chrome_profile").resolve()
        self.nexus_profiles_root = (self.data_root / "browser_profiles" / "nexus_browser").resolve()
        self.downloads_dir = (self.data_root / "downloads").resolve()

        self.ultron_chrome_profile.mkdir(parents=True, exist_ok=True)
        (self.nexus_profiles_root / "default").mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        self._assert_profile_strictly_isolated(self.ultron_chrome_profile)

        self._tabs: list[dict[str, Any]] = [
            {
                "tab_id": "tab_home",
                "profile": "default",
                "title": "NEXUS Browser Home",
                "url": "nexus://home",
                "status": "ready",
                "content_preview": "NEXUS Browser Ready — Protected by Multi-Layer Payment Isolation Shield.",
            }
        ]
        self._active_tab_id: str = "tab_home"
        self._http_transport: httpx.BaseTransport | None = None

    def set_http_transport(self, transport: httpx.BaseTransport | None) -> None:
        self._http_transport = transport

    @staticmethod
    def _assert_profile_strictly_isolated(profile_dir: Path) -> None:
        """Guarantee ULTRON's Chrome profile never overlaps with the user's personal Chrome User Data."""
        user_chrome = _get_user_default_chrome_profile_dir().resolve()
        resolved = profile_dir.resolve()
        if resolved == user_chrome or user_chrome in resolved.parents:
            raise PermissionError(
                f"CRITICAL ISOLATION VIOLATION: Profile path {resolved} overlaps user's personal Chrome directory {user_chrome}"
            )

    def get_chrome_isolation_status(self) -> dict[str, Any]:
        user_chrome = _get_user_default_chrome_profile_dir()
        self._assert_profile_strictly_isolated(self.ultron_chrome_profile)
        chrome_bin = _find_system_chrome_binary()
        return {
            "chrome_binary_detected": bool(chrome_bin),
            "chrome_binary_path": chrome_bin,
            "ultron_isolated_profile_dir": str(self.ultron_chrome_profile),
            "user_personal_chrome_dir": str(user_chrome),
            "user_chrome_untouched": True,
            "cookies_or_passwords_copied": False,
        }

    def build_isolated_chrome_launch_args(self, target_url: str = "about:blank") -> list[str]:
        """Build command-line arguments launching Chrome strictly inside ULTRON's isolated profile."""
        self.permissions.require_permission("browser_access", actor="browser_agent", action_desc=f"chrome {target_url}")
        self.payment_shield.assert_safe_for_browser(target_url)
        self._assert_profile_strictly_isolated(self.ultron_chrome_profile)

        chrome_bin = _find_system_chrome_binary() or "chrome"
        return [
            chrome_bin,
            f"--user-data-dir={self.ultron_chrome_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
            target_url,
        ]

    def launch_isolated_chrome(self, target_url: str = "https://www.google.com") -> dict[str, Any]:
        args = self.build_isolated_chrome_launch_args(target_url)
        chrome_bin = _find_system_chrome_binary()
        if not chrome_bin:
            return {
                "launched": False,
                "reason": "Google Chrome binary not installed on this host; isolated profile configured and ready.",
                "launch_args": args,
                "isolated_profile_dir": str(self.ultron_chrome_profile),
            }
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "launched": True,
            "pid": proc.pid,
            "launch_args": args,
            "isolated_profile_dir": str(self.ultron_chrome_profile),
        }

    # --- NEXUS Browser Multi-Tab, Profiles, Search, Bookmarks, History & Downloads ---
    def create_profile(self, profile_name: str) -> Path:
        safe_name = "".join(c for c in profile_name if c.isalnum() or c in "-_").strip() or "custom"
        pdir = self.nexus_profiles_root / safe_name
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def list_profiles(self) -> list[str]:
        return sorted(p.name for p in self.nexus_profiles_root.iterdir() if p.is_dir())

    def open_tab(
        self,
        url_or_query: str,
        profile: str = "default",
        simulated_html: str | None = None,
    ) -> dict[str, Any]:
        self.permissions.require_permission("browser_access", actor="nexus_browser", action_desc=f"open_tab {url_or_query}")
        self.create_profile(profile)
        tab_id = f"tab_{uuid.uuid4().hex[:8]}"
        tab = {"tab_id": tab_id, "profile": profile, "title": "Loading...", "url": "nexus://newtab", "status": "loading", "content_preview": ""}
        self._tabs.append(tab)
        self._active_tab_id = tab_id
        return self.navigate_tab(tab_id, url_or_query, simulated_html=simulated_html)

    def close_tab(self, tab_id: str) -> bool:
        before = len(self._tabs)
        self._tabs = [t for t in self._tabs if t["tab_id"] != tab_id]
        if not self._tabs:
            self._tabs.append(
                {
                    "tab_id": "tab_home",
                    "profile": "default",
                    "title": "NEXUS Browser Home",
                    "url": "nexus://home",
                    "status": "ready",
                    "content_preview": "NEXUS Browser Ready.",
                }
            )
        self._active_tab_id = self._tabs[-1]["tab_id"]
        return len(self._tabs) < before

    def list_tabs(self) -> list[dict[str, Any]]:
        return [dict(t) for t in self._tabs]

    def navigate_tab(
        self,
        tab_id: str,
        url_or_query: str,
        simulated_html: str | None = None,
    ) -> dict[str, Any]:
        """Navigate a NEXUS Browser tab, enforcing Payment Isolation on both URL and DOM."""
        self.permissions.require_permission("browser_access", actor="nexus_browser", action_desc=f"navigate {url_or_query}")
        tab = next((t for t in self._tabs if t["tab_id"] == tab_id), None)
        if not tab:
            raise KeyError(f"Browser tab not found: {tab_id}")

        raw = (url_or_query or "").strip()
        if raw in CONFIGURED_PLATFORMS:
            target_url = CONFIGURED_PLATFORMS[raw]
        elif "://" in raw or raw.startswith("nexus:"):
            target_url = raw
        elif "." in raw and " " not in raw:
            target_url = f"https://{raw}"
        else:
            target_url = f"https://www.google.com/search?q={quote_plus(raw)}"

        # Layer 1 Payment Isolation URL check BEFORE network request
        url_verdict = self.payment_shield.inspect_url(target_url)
        if url_verdict.isolated:
            self._record_history(tab["profile"], "BLOCKED PAYMENT WORKFLOW", target_url, blocked=True)
            tab.update(
                {
                    "url": target_url,
                    "title": "Payment Isolation Active — Manual User Control Only",
                    "status": "isolated_payment_workflow",
                    "content_preview": (
                        "ULTRON automation & DOM access suspended for this financial/checkout page. "
                        "Complete any payment independently in your personal browser."
                    ),
                }
            )
            raise PaymentIsolationTriggered(f"PAYMENT ISOLATION [{url_verdict.source_layer}]: {url_verdict.reason}")

        html_body = simulated_html
        status = "loaded"
        if html_body is None and not target_url.startswith("nexus://"):
            if self._http_transport is not None:
                with httpx.Client(timeout=10.0, follow_redirects=True, transport=self._http_transport) as client:
                    resp = client.get(target_url)
                    html_body = resp.text
            else:
                # Lightweight safe metadata state when browsing offline or opening external platform URL
                html_body = f"<html><head><title>{target_url}</title></head><body>Connected target: {target_url}</body></html>"

        # Layer 2 Payment Isolation DOM check BEFORE exposing DOM to any ULTRON agent!
        if html_body is not None:
            dom_verdict = self.payment_shield.inspect_dom(html_body, page_url=target_url)
            if dom_verdict.isolated:
                self._record_history(tab["profile"], "BLOCKED PAYMENT DOM", target_url, blocked=True)
                tab.update(
                    {
                        "url": target_url,
                        "title": "Protected Checkout Fields Detected — Automation Halted",
                        "status": "isolated_payment_workflow",
                        "content_preview": "[DOM ACCESS BLOCKED BY PAYMENT ISOLATION ENGINE]",
                    }
                )
                raise PaymentIsolationTriggered(f"PAYMENT ISOLATION [{dom_verdict.source_layer}]: {dom_verdict.reason}")

        sanitized = self.prompt_shield.inspect_and_wrap((html_body or "")[:2000], source=target_url)
        title = target_url.replace("https://", "").replace("http://", "")[:60]
        tab.update(
            {
                "url": target_url,
                "title": title,
                "status": status,
                "content_preview": sanitized.safe_text[:600],
            }
        )
        self._record_history(tab["profile"], title, target_url, blocked=False)
        return dict(tab)

    def inspect_tab_dom_for_agent(self, tab_id: str, raw_dom: str | None) -> str:
        """Safe DOM accessor for agents — fails closed on None or payment fields."""
        tab = next((t for t in self._tabs if t["tab_id"] == tab_id), None)
        page_url = tab["url"] if tab else "unknown"
        verdict = self.payment_shield.inspect_dom(raw_dom, page_url=page_url)
        if verdict.isolated:
            raise PaymentIsolationTriggered(f"DOM inspection blocked [{verdict.source_layer}]: {verdict.reason}")
        return self.prompt_shield.inspect_and_wrap(raw_dom or "", source=page_url).safe_text

    def add_bookmark(self, title: str, url: str, profile: str = "default") -> dict[str, Any]:
        bid = f"bm_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO browser_bookmarks (id, profile_name, title, url, created_at) VALUES (?, ?, ?, ?, ?)",
            (bid, profile, title.strip(), url.strip(), now),
        )
        return {"id": bid, "profile_name": profile, "title": title, "url": url, "created_at": now}

    def list_bookmarks(self, profile: str = "default") -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM browser_bookmarks WHERE profile_name = ? ORDER BY created_at DESC",
            (profile,),
        )

    def list_history(self, profile: str = "default", limit: int = 50) -> list[dict[str, Any]]:
        return self.db.query_all(
            "SELECT * FROM browser_history WHERE profile_name = ? ORDER BY visited_at DESC LIMIT ?",
            (profile, limit),
        )

    def download_file(self, url: str, filename: str | None = None, profile: str = "default") -> dict[str, Any]:
        self.permissions.require_permission("browser_access", actor="browser_agent", action_desc=f"download {url}")
        self.payment_shield.assert_safe_for_browser(url)

        safe_name = Path(filename or url.split("/")[-1] or "download.bin").name
        dest = self.downloads_dir / safe_name
        with httpx.Client(timeout=30.0, follow_redirects=True, transport=self._http_transport) as client:
            resp = client.get(url)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        did = f"dl_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO browser_downloads (id, profile_name, url, file_path, size_bytes, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'completed', ?)
            """,
            (did, profile, url, str(dest), dest.stat().st_size, now),
        )
        return {"id": did, "url": url, "file_path": str(dest), "size_bytes": dest.stat().st_size, "status": "completed"}

    def list_downloads(self, limit: int = 30) -> list[dict[str, Any]]:
        return self.db.query_all("SELECT * FROM browser_downloads ORDER BY created_at DESC LIMIT ?", (limit,))

    def _record_history(self, profile: str, title: str, url: str, blocked: bool) -> None:
        hid = f"bh_{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            """
            INSERT INTO browser_history (id, profile_name, title, url, blocked_by_payment_shield, visited_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (hid, profile, title[:120], url[:250], 1 if blocked else 0, now),
        )
