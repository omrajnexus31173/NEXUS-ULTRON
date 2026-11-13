"""Automated Verification of the FastAPI Web Command Center (no PySide6 required)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nexus_ultron.runtime import NexusUltronRuntime
from nexus_ultron.web_ui.server import create_web_app


def test_web_command_center_api_and_plugins(offline_runtime: NexusUltronRuntime) -> None:
    """Verify FastAPI Web Command Center endpoints, Brand Kit, and Plugin error isolation."""
    client = TestClient(create_web_app(offline_runtime))

    assert client.get("/").status_code == 200
    ov = client.get("/api/overview").json()
    assert ov["app_name"] == "NEXUS ULTRON"

    calc = client.post("/api/files/calculate", json={"expression": "12 * 12"}).json()
    assert calc["result"] == 144

    skills = client.get("/api/plugins").json()
    assert len(skills) >= 4
    exec_res = client.post(
        "/api/plugins/execute",
        json={"skill_id": "security_posture_auditor", "params": {}},
    ).json()
    assert exec_res["ok"] is True
    assert exec_res["result"]["audit_chain_valid"] is True

    # Blocked payment URL returns HTTP 403 via Payment Shield
    blocked = client.post("/api/browser/navigate", json={"url_or_query": "https://checkout.stripe.com/pay/test"})
    assert blocked.status_code == 403

    kit = client.get("/api/brand-kit").json()
    assert len(kit) >= 6
