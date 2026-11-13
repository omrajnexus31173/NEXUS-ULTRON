"""QA Scenarios #14, #15, #16, #17: Isolated Chrome, NEXUS Browser, Gmail OAuth2 & Test-Account OTP Security."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
import pytest

from nexus_ultron.runtime import NexusUltronRuntime
from nexus_ultron.security.credential_vault import CredentialVaultError


def test_14_and_15_isolated_chrome_and_nexus_browser(offline_runtime: NexusUltronRuntime) -> None:
    """Tests #14 (Isolated ULTRON Chrome profile) & #15 (NEXUS Browser multi-tab, bookmarks, downloads)."""
    iso = offline_runtime.browser.get_chrome_isolation_status()
    assert iso["user_chrome_untouched"] is True
    assert iso["cookies_or_passwords_copied"] is False
    assert iso["ultron_isolated_profile_dir"] != iso["user_personal_chrome_dir"]

    args = offline_runtime.browser.build_isolated_chrome_launch_args("https://docs.python.org/3/")
    assert any(a.startswith("--user-data-dir=") and "ultron_chrome_profile" in a for a in args)

    # NEXUS Browser tabs, separate profiles, bookmarks, history & download manager
    offline_runtime.browser.set_http_transport(
        httpx.MockTransport(lambda req: httpx.Response(200, text=f"<html><body>Safe docs for {req.url}</body></html>"))
    )
    tab = offline_runtime.browser.open_tab("https://docs.python.org/3/library/sqlite3.html", profile="research")
    assert tab["status"] == "loaded"
    assert "research" in offline_runtime.browser.list_profiles()

    bm = offline_runtime.browser.add_bookmark("SQLite Docs", tab["url"], profile="research")
    assert len(offline_runtime.browser.list_bookmarks(profile="research")) == 1 and bm["title"] == "SQLite Docs"

    dl = offline_runtime.browser.download_file("https://docs.python.org/3/readme.txt", filename="python_readme.txt")
    assert Path(dl["file_path"]).exists()
    assert offline_runtime.browser.close_tab(tab["tab_id"]) is True


def test_16_and_17_authorized_gmail_oauth_and_otp_redaction(offline_runtime: NexusUltronRuntime) -> None:
    """Tests #16 (Authorized Gmail OAuth2) & #17 (Test-account OTP matching, expiry, mobile handoff & zero log leakage)."""
    # Raw Gmail password storage must be strictly prohibited
    with pytest.raises(CredentialVaultError):
        offline_runtime.vault.set_secret("gmail_raw_password", "hunter2")

    # Verify OAuth2 PKCE URL generation
    pkce = offline_runtime.gmail.build_oauth2_pkce_authorization_url("test-client-id.apps.googleusercontent.com")
    assert "code_challenge=" in pkce["authorization_url"]
    assert "gmail.readonly" in pkce["authorization_url"]

    # Enable explicit OTP retrieval permission for test session
    offline_runtime.permissions.set_permission("authorized_email_reading", True)
    offline_runtime.permissions.set_permission("otp_retrieval", True)

    now = datetime.now(timezone.utc)
    secret_otp = "849206"
    expired_otp = "112233"

    offline_runtime.gmail.inject_test_messages(
        [
            {
                "id": "m_valid",
                "sender": "no-reply@github-test-portal.example",
                "subject": "Your Login Code",
                "body": f"Your verification code is {secret_otp}. Valid for 5 minutes.",
                "received_at": now.isoformat(),
            },
            {
                "id": "m_expired",
                "sender": "auth@expired-portal.example",
                "subject": "Expired Login Code",
                "body": f"Your verification code is {expired_otp}.",
                "received_at": (now - timedelta(minutes=20)).isoformat(),
            },
            {
                "id": "m_mobile",
                "sender": "security@mobile-mfa-portal.example",
                "subject": "2FA Notice",
                "body": "SMS verification sent to your mobile device. Please approve on your phone.",
                "received_at": now.isoformat(),
            },
        ]
    )

    # 1. Valid active login session matches & applies OTP via callback
    applied_codes: list[str] = []
    offline_runtime.gmail.start_auth_session("sess_gh", "github-test-portal.example", "dev@example.com")
    res_valid = offline_runtime.gmail.match_and_apply_login_otp("sess_gh", target_field_callback=applied_codes.append)
    assert res_valid["status"] == "authenticated"
    assert res_valid["otp_applied"] is True
    assert applied_codes == [secret_otp]
    # Raw OTP must NOT be returned in summary dict, logs, or audit trail!
    assert secret_otp not in str(res_valid)

    offline_runtime.logger.info(f"Attempting accidental log of OTP {secret_otp}")
    all_logs = "\n".join(item["message"] for item in offline_runtime.logging_engine.recent_logs(200))
    log_disk = offline_runtime.logging_engine.log_file.read_text(encoding="utf-8")
    assert secret_otp not in all_logs
    assert secret_otp not in log_disk

    # 2. Expired OTP detected accurately
    offline_runtime.gmail.start_auth_session("sess_exp", "expired-portal.example")
    res_exp = offline_runtime.gmail.match_and_apply_login_otp("sess_exp")
    assert res_exp["expired"] is True and res_exp["otp_applied"] is False

    # 3. Mobile SMS / MFA prompts user intervention cleanly
    offline_runtime.gmail.start_auth_session("sess_mob", "mobile-mfa-portal.example")
    res_mob = offline_runtime.gmail.match_and_apply_login_otp("sess_mob")
    assert res_mob["status"] == "user_intervention_required"
