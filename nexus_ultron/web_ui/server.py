"""FastAPI Server exposing all 14 NEXUS ULTRON subsystems + Brand & Release Downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..agents.base_agent import BaseAgent, SharedTaskContext
from ..intelligence.file_intelligence import safe_calculate
from ..runtime import NexusUltronRuntime
from ..security.payment_isolation import PaymentIsolationTriggered
from ..security.permission_engine import PermissionDeniedError


class ChatRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None
    preferred_provider: str | None = None


class ObjectiveRequest(BaseModel):
    objective: str
    priority: int = 7


class BuildAppRequest(BaseModel):
    objective: str
    language: str = "python"


class MemoryCreateRequest(BaseModel):
    title: str
    content: str
    namespace: str = "long_term"
    tags: list[str] = []


class BrowserNavRequest(BaseModel):
    url_or_query: str
    profile: str = "default"


class PermissionUpdateRequest(BaseModel):
    category: str | None = None
    granted: bool | None = None
    profile_name: str | None = None


class ModePolicyRequest(BaseModel):
    policy: str


class VaultSecretRequest(BaseModel):
    key_name: str
    secret_value: str


class VoiceTurnRequest(BaseModel):
    utterance: str
    wake_word: str | None = None


class DynamicAgentRequest(BaseModel):
    agent_id: str
    display_name: str
    specialty: str


class SkillExecRequest(BaseModel):
    skill_id: str
    params: dict[str, Any] = {}


class FileCalcRequest(BaseModel):
    expression: str


class _WebCustomAgent(BaseAgent):
    def __init__(self, agent_id: str, display_name: str, specialty: str) -> None:
        self.agent_id = agent_id
        self.display_name = display_name
        self.specialty = specialty

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        return {"agent": self.agent_id, "status": "completed", "subtask": subtask["title"]}


def create_web_app(runtime: NexusUltronRuntime | None = None) -> FastAPI:
    rt = runtime or NexusUltronRuntime()
    app = FastAPI(
        title="NEXUS ULTRON — Autonomous Personal AI Operating System",
        version="3.0.0",
    )
    app.state.runtime = rt

    # Allow Arena iframe / preview hosts cleanly
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    branding_dir = rt.repo_root / "assets" / "branding"
    releases_dir = rt.repo_root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    if branding_dir.exists():
        app.mount("/branding", StaticFiles(directory=str(branding_dir)), name="branding")
    app.mount("/releases", StaticFiles(directory=str(releases_dir)), name="releases")

    @app.get("/", response_class=HTMLResponse)
    def serve_index() -> str:
        return (static_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/api/overview")
    def api_overview() -> dict[str, Any]:
        releases = [
            {"name": p.name, "size_kb": round(p.stat().st_size / 1024, 1), "url": f"/releases/{p.name}"}
            for p in sorted(releases_dir.glob("*"))
            if p.is_file()
        ]
        return {**rt.dashboard_overview(), "releases": releases}

    @app.post("/api/chat")
    def api_chat(req: ChatRequest) -> dict[str, Any]:
        conv_id = req.conversation_id
        if not conv_id:
            conv = rt.memory.create_conversation(req.prompt[:40] or "Session", rt.connectivity.effective_mode)
            conv_id = conv["id"]
        res = rt.ai_router.generate_response(
            req.prompt,
            conversation_id=conv_id,
            preferred_provider=req.preferred_provider,
        )
        return {**res, "conversation_id": conv_id, "messages": rt.memory.get_conversation_messages(conv_id)}

    @app.get("/api/tasks")
    def api_list_tasks() -> list[dict[str, Any]]:
        return rt.planner.list_tasks(limit=40)

    @app.post("/api/tasks")
    def api_run_task(req: ObjectiveRequest) -> dict[str, Any]:
        try:
            return rt.orchestrator.run_objective_sync(
                objective=req.objective,
                priority=req.priority,
                mode_used=rt.connectivity.effective_mode,
            )
        except (PaymentIsolationTriggered, PermissionDeniedError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/tasks/{task_id}/cancel")
    def api_cancel_task(task_id: str) -> dict[str, Any]:
        return rt.planner.cancel_task(task_id)

    @app.get("/api/agents")
    def api_agents() -> list[dict[str, Any]]:
        return rt.orchestrator.list_agents()

    @app.post("/api/agents")
    def api_register_agent(req: DynamicAgentRequest) -> dict[str, Any]:
        rt.orchestrator.register_agent(_WebCustomAgent(req.agent_id, req.display_name, req.specialty))
        return {"registered": req.agent_id, "agents": rt.orchestrator.list_agents()}

    @app.get("/api/browser")
    def api_browser_state() -> dict[str, Any]:
        return {
            "chrome_isolation": rt.browser.get_chrome_isolation_status(),
            "tabs": rt.browser.list_tabs(),
            "bookmarks": rt.browser.list_bookmarks(),
            "history": rt.browser.list_history(limit=25),
            "downloads": rt.browser.list_downloads(limit=20),
        }

    @app.post("/api/browser/navigate")
    def api_browser_navigate(req: BrowserNavRequest) -> dict[str, Any]:
        try:
            return rt.browser.open_tab(req.url_or_query, profile=req.profile)
        except (PaymentIsolationTriggered, PermissionDeniedError) as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/api/models")
    def api_models() -> dict[str, Any]:
        return {"providers": rt.ai_router.list_providers(), "stored_keys": rt.vault.list_stored_keys()}

    @app.post("/api/models/secret")
    def api_store_secret(req: VaultSecretRequest) -> dict[str, Any]:
        try:
            backend = rt.vault.set_secret(req.key_name, req.secret_value)
            return {"stored": req.key_name, "backend": backend, "providers": rt.ai_router.list_providers()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/memory")
    def api_memory(q: str = "", namespace: str = "") -> dict[str, Any]:
        ns = namespace or None
        items = rt.memory.search_memory(q, namespace=ns) if q else rt.memory.list_memories(namespace=ns)
        return {"memories": items, "notes_reminders": rt.memory.list_notes_reminders()}

    @app.post("/api/memory")
    def api_add_memory(req: MemoryCreateRequest) -> dict[str, Any]:
        try:
            return rt.memory.add_memory(req.title, req.content, namespace=req.namespace, tags=req.tags)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/memory/{entry_id}")
    def api_delete_memory(entry_id: str) -> dict[str, Any]:
        return {"deleted": rt.memory.delete_memory(entry_id)}

    @app.get("/api/files/search")
    def api_search_files(pattern: str = "*.md", q: str = "") -> list[dict[str, Any]]:
        try:
            return rt.file_intel.search_files(rt.repo_root, pattern=pattern, content_query=q or None)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/files/calculate")
    def api_calc(req: FileCalcRequest) -> dict[str, Any]:
        try:
            return {"expression": req.expression, "result": safe_calculate(req.expression)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/developer/projects")
    def api_projects() -> list[dict[str, Any]]:
        return rt.dev_engine.list_projects()

    @app.post("/api/developer/build")
    def api_build_app(req: BuildAppRequest) -> dict[str, Any]:
        try:
            return rt.dev_engine.build_application(req.objective, requested_language=req.language)
        except PermissionDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.get("/api/system")
    def api_system() -> dict[str, Any]:
        return {
            "snapshot": rt.resources.snapshot(),
            "hardware": rt.hardware.to_dict(),
            "processes": rt.resources.list_top_processes(limit=15),
        }

    @app.get("/api/security")
    def api_security() -> dict[str, Any]:
        valid_chain, count = rt.audit.verify_integrity()
        return {
            "emergency_stop_active": rt.permissions.emergency_stop_active,
            "payment_isolation_locked": rt.payment_shield.is_locked_down,
            "payment_lockdown_reason": rt.payment_shield.lockdown_reason,
            "grants": rt.permissions.get_grants(),
            "profiles": rt.permissions.list_profiles(),
            "audit_chain_valid": valid_chain,
            "audit_entry_count": count,
            "audit_events": rt.audit.list_events(limit=40),
            "payment_events": rt.payment_shield.list_events(limit=20),
        }

    @app.post("/api/security/permissions")
    def api_update_permissions(req: PermissionUpdateRequest) -> dict[str, Any]:
        try:
            if req.profile_name:
                grants = rt.permissions.apply_profile(req.profile_name)
            elif req.category is not None and req.granted is not None:
                rt.permissions.set_permission(req.category, req.granted)
                grants = rt.permissions.get_grants()
            else:
                grants = rt.permissions.get_grants()
            return {"grants": grants}
        except Exception as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/api/security/revoke-all")
    def api_revoke_all() -> dict[str, Any]:
        return {"grants": rt.permissions.revoke_all_permissions()}

    @app.post("/api/security/emergency-stop")
    def api_emergency_stop() -> dict[str, Any]:
        if rt.permissions.emergency_stop_active:
            return rt.permissions.reset_emergency_stop()
        return rt.permissions.trigger_emergency_stop("Triggered via Command Center UI")

    @app.post("/api/security/release-payment-lock")
    def api_release_payment() -> dict[str, Any]:
        rt.payment_shield.release_user_completed_payment()
        return {"payment_isolation_locked": rt.payment_shield.is_locked_down}

    @app.get("/api/plugins")
    def api_plugins() -> list[dict[str, Any]]:
        return rt.plugins.list_skills()

    @app.post("/api/plugins/execute")
    def api_exec_plugin(req: SkillExecRequest) -> dict[str, Any]:
        return rt.plugins.execute_skill(req.skill_id, req.params)

    @app.post("/api/plugins/{skill_id}/toggle")
    def api_toggle_plugin(skill_id: str) -> dict[str, Any]:
        info = rt.plugins.get_skill_info(skill_id)
        return rt.plugins.set_enabled(skill_id, not info["enabled"])

    @app.get("/api/voice")
    def api_voice_settings() -> dict[str, Any]:
        return {"settings": rt.voice.get_settings(), "microphones": rt.voice.list_microphones()}

    @app.post("/api/voice/turn")
    def api_voice_turn(req: VoiceTurnRequest) -> dict[str, Any]:
        if req.wake_word:
            rt.voice.update_settings(wake_word=req.wake_word)
        return rt.voice.process_voice_turn(req.utterance, require_wake_word=False)

    @app.post("/api/voice/interrupt")
    def api_voice_interrupt() -> dict[str, Any]:
        return rt.voice.interrupt_speech()

    @app.post("/api/settings/mode")
    def api_set_mode(req: ModePolicyRequest) -> dict[str, Any]:
        rt.config.set("mode_policy", req.policy)
        return rt.connectivity.set_policy(req.policy)

    @app.get("/api/brand-kit")
    def api_brand_kit() -> list[dict[str, str]]:
        return [
            {"title": "1. Primary Horizontal Logo", "file": "logo_primary_horizontal.png", "url": "/branding/logo_primary_horizontal.png"},
            {"title": "2. Standalone Emblem", "file": "logo_emblem_standalone.png", "url": "/branding/logo_emblem_standalone.png"},
            {"title": "3. Square Desktop App Icon", "file": "logo_app_icon_square.png", "url": "/branding/logo_app_icon_square.png"},
            {"title": "4. Monochrome Black & White", "file": "logo_monochrome_bw.png", "url": "/branding/logo_monochrome_bw.png"},
            {"title": "5. Transparent Background PNG", "file": "logo_transparent_horizontal.png", "url": "/branding/logo_transparent_horizontal.png"},
            {"title": "6. Scalable Vector Identity (SVG)", "file": "logo_vector.svg", "url": "/branding/logo_vector.svg"},
            {"title": "7. PySide6 Native Desktop Render", "file": "desktop_dashboard_preview.png", "url": "/branding/desktop_dashboard_preview.png"},
        ]

    @app.get("/favicon.ico")
    def favicon() -> FileResponse:
        return FileResponse(str(branding_dir / "nexus_ultron.ico"))

    return app
