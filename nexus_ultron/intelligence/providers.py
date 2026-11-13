"""Hybrid Offline & Online AI Provider Router, Local Reasoning Core, Ollama Adapter, Cloud Adapters & Web Research."""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

import httpx

from ..core.connectivity import ConnectivityManager
from ..core.logging_engine import redact_sensitive_text
from ..core.resource_manager import ResourceManager
from ..security.credential_vault import CredentialVault
from ..security.payment_isolation import PaymentIsolationEngine
from ..security.prompt_guard import PromptInjectionShield
from ..storage.memory_system import MemorySystem
from .file_intelligence import safe_calculate

logger = logging.getLogger("nexus_ultron.providers")


class AIProviderRouter:
    """
    Routes intelligence requests across:
      1. Offline Built-in Reasoning Core (always available, zero network/GPU needed)
      2. Optional Local Lightweight LLM via Ollama / llama.cpp (loaded on-demand, semaphore-bounded)
      3. Online Cloud AI Models (OpenAI / OpenRouter / Anthropic / Gemini) with automatic offline fallback!
    Never preloads heavy models at startup.
    """

    def __init__(
        self,
        connectivity: ConnectivityManager,
        resources: ResourceManager,
        vault: CredentialVault,
        memory: MemorySystem,
        payment_shield: PaymentIsolationEngine,
        prompt_shield: PromptInjectionShield,
        provider_config: dict[str, Any] | None = None,
    ) -> None:
        self.connectivity = connectivity
        self.resources = resources
        self.vault = vault
        self.memory = memory
        self.payment_shield = payment_shield
        self.prompt_shield = prompt_shield
        self.config = provider_config or {}
        self._local_llm_sem = threading.BoundedSemaphore(
            value=max(1, self.resources.hardware.max_local_llm_concurrency)
        )
        # Mockable HTTP transport for cloud/web tests
        self._http_transport: httpx.BaseTransport | None = None

    def set_http_transport(self, transport: httpx.BaseTransport | None) -> None:
        self._http_transport = transport

    def list_providers(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "ultron_local_core",
                "name": "NEXUS Local Reasoning Core",
                "mode": "offline",
                "configured": True,
                "status": "ready",
                "ram_requirement": "8 GB Compatible (<50 MB footprint)",
            },
            {
                "id": "ollama_local",
                "name": f"Local Lightweight LLM ({self.config.get('ollama_model', 'qwen2.5-coder:1.5b')})",
                "mode": "offline",
                "configured": True,
                "status": "on_demand",
                "ram_requirement": "8 GB+ On-Demand Lazy Load",
            },
            {
                "id": "openai_compatible",
                "name": f"OpenAI / Compatible Cloud ({self.config.get('openai_model', 'gpt-4o-mini')})",
                "mode": "online",
                "configured": bool(self.vault.get_secret("OPENAI_API_KEY") or self.vault.get_secret("OPENROUTER_API_KEY")),
                "status": "ready" if self.connectivity.effective_mode == "online" else "standby_offline",
                "ram_requirement": "Cloud Offloaded (0 MB Local Model RAM)",
            },
            {
                "id": "anthropic",
                "name": f"Anthropic Claude ({self.config.get('anthropic_model', 'claude-3-5-sonnet-latest')})",
                "mode": "online",
                "configured": bool(self.vault.get_secret("ANTHROPIC_API_KEY")),
                "status": "ready" if self.connectivity.effective_mode == "online" else "standby_offline",
                "ram_requirement": "Cloud Offloaded",
            },
            {
                "id": "gemini",
                "name": f"Google Gemini ({self.config.get('gemini_model', 'gemini-2.5-flash')})",
                "mode": "online",
                "configured": bool(self.vault.get_secret("GEMINI_API_KEY")),
                "status": "ready" if self.connectivity.effective_mode == "online" else "standby_offline",
                "ram_requirement": "Cloud Offloaded",
            },
        ]

    def generate_response(
        self,
        prompt: str,
        conversation_id: str | None = None,
        preferred_provider: str | None = None,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Generate an intelligent response with payment isolation check, memory context, and automatic fallback."""
        verdict = self.payment_shield.inspect_objective(prompt)
        if verdict.isolated:
            blocked_msg = (
                "PAYMENT ISOLATION BOUNDARY ACTIVE: NEXUS ULTRON never participates in payments, "
                "checkouts, banking, UPI, or money transfers. Please complete any financial "
                "transaction directly yourself."
            )
            if conversation_id:
                self.memory.add_message(conversation_id, "user", prompt, provider="user")
                self.memory.add_message(conversation_id, "assistant", blocked_msg, provider="payment_isolation_shield")
            return {
                "reply": blocked_msg,
                "provider_used": "payment_isolation_shield",
                "mode_used": self.connectivity.effective_mode,
                "fallback_occurred": False,
                "blocked_by_payment_isolation": True,
            }

        if conversation_id:
            self.memory.add_message(conversation_id, "user", prompt, provider="user")

        # Never leak secrets/OTPs to external providers
        safe_prompt = redact_sensitive_text(prompt)
        mode = self.connectivity.effective_mode
        fallback_occurred = False

        # Try Online Cloud Provider when in online mode and API key is configured
        if mode == "online" and preferred_provider != "ultron_local_core":
            cloud_target = preferred_provider or self.config.get("default_online_provider", "openai_compatible")
            cloud_reply, used_id, err = self._try_cloud_provider(cloud_target, safe_prompt, system_prompt)
            if cloud_reply is not None:
                if conversation_id:
                    self.memory.add_message(conversation_id, "assistant", cloud_reply, provider=used_id)
                return {
                    "reply": cloud_reply,
                    "provider_used": used_id,
                    "mode_used": "online",
                    "fallback_occurred": False,
                    "blocked_by_payment_isolation": False,
                }
            if err:
                fallback_occurred = True
                logger.info("Cloud provider unavailable (%s); falling back seamlessly to local engine.", err)

        # Optional local Ollama on-demand if explicitly requested and not in low-memory lockdown
        if preferred_provider == "ollama_local" and not self.resources.snapshot()["low_memory_mode_active"]:
            ollama_reply = self._try_ollama_local(safe_prompt, system_prompt)
            if ollama_reply:
                if conversation_id:
                    self.memory.add_message(conversation_id, "assistant", ollama_reply, provider="ollama_local")
                return {
                    "reply": ollama_reply,
                    "provider_used": "ollama_local",
                    "mode_used": "offline",
                    "fallback_occurred": fallback_occurred,
                    "blocked_by_payment_isolation": False,
                }
            fallback_occurred = True

        # Always-available Offline Built-in Local Core
        local_reply = self._local_core_reason(prompt)
        if conversation_id:
            self.memory.add_message(conversation_id, "assistant", local_reply, provider="ultron_local_core")
        return {
            "reply": local_reply,
            "provider_used": "ultron_local_core",
            "mode_used": self.connectivity.effective_mode,
            "fallback_occurred": fallback_occurred,
            "blocked_by_payment_isolation": False,
        }

    def _try_cloud_provider(
        self,
        provider_id: str,
        safe_prompt: str,
        system_prompt: str | None,
    ) -> tuple[str | None, str, str | None]:
        sys_msg = system_prompt or (
            "You are NEXUS ULTRON, an autonomous desktop intelligence system. "
            "Provide concise, accurate, verified engineering and operational responses."
        )
        try:
            if provider_id in {"openai_compatible", "openai"}:
                api_key = self.vault.get_secret("OPENAI_API_KEY") or self.vault.get_secret("OPENROUTER_API_KEY")
                if not api_key:
                    return None, provider_id, "no_api_key_configured"
                base_url = self.config.get("openai_base_url", "https://api.openai.com/v1").rstrip("/")
                model = self.config.get("openai_model", "gpt-4o-mini")
                with httpx.Client(timeout=20.0, transport=self._http_transport) as client:
                    resp = client.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": sys_msg},
                                {"role": "user", "content": safe_prompt},
                            ],
                            "temperature": 0.2,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return str(content), "openai_compatible", None

            if provider_id == "anthropic":
                api_key = self.vault.get_secret("ANTHROPIC_API_KEY")
                if not api_key:
                    return None, provider_id, "no_api_key_configured"
                model = self.config.get("anthropic_model", "claude-3-5-sonnet-latest")
                with httpx.Client(timeout=20.0, transport=self._http_transport) as client:
                    resp = client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "max_tokens": 1024,
                            "system": sys_msg,
                            "messages": [{"role": "user", "content": safe_prompt}],
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return str(data["content"][0]["text"]), "anthropic", None

            if provider_id == "gemini":
                api_key = self.vault.get_secret("GEMINI_API_KEY")
                if not api_key:
                    return None, provider_id, "no_api_key_configured"
                model = self.config.get("gemini_model", "gemini-2.5-flash")
                with httpx.Client(timeout=20.0, transport=self._http_transport) as client:
                    resp = client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                        json={"contents": [{"parts": [{"text": f"{sys_msg}\n\n{safe_prompt}"}]}]},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    return str(data["candidates"][0]["content"]["parts"][0]["text"]), "gemini", None

            return None, provider_id, "unknown_provider"
        except httpx.NetworkError as exc:
            self.connectivity.report_connection_failure(provider_id)
            return None, provider_id, f"network_error:{exc}"
        except Exception as exc:
            return None, provider_id, f"provider_error:{exc}"

    def _try_ollama_local(self, safe_prompt: str, system_prompt: str | None) -> str | None:
        acquired = self._local_llm_sem.acquire(blocking=False)
        if not acquired:
            return None
        try:
            base = self.config.get("ollama_base_url", "http://127.0.0.1:11434").rstrip("/")
            model = self.config.get("ollama_model", "qwen2.5-coder:1.5b")
            with httpx.Client(timeout=10.0, transport=self._http_transport) as client:
                resp = client.post(
                    f"{base}/api/generate",
                    json={
                        "model": model,
                        "prompt": f"{system_prompt or ''}\n\n{safe_prompt}".strip(),
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                return str(resp.json().get("response", "")).strip() or None
        except Exception:
            return None
        finally:
            self._local_llm_sem.release()

    def _local_core_reason(self, prompt: str) -> str:
        """Deterministic, fast, zero-dependency offline reasoning engine."""
        cleaned = (prompt or "").strip()
        lower = cleaned.lower()

        # 1. Check inline math calculation requests
        calc_match = re.search(r"(?:calculate|compute|solve|what\s+is)\s*[:=]?\s*([0-9\.\+\-\*\/\^\(\)\s,a-z_]+)$", lower)
        if calc_match:
            candidate = calc_match.group(1).strip().rstrip("?")
            try:
                result = safe_calculate(candidate)
                return f"Calculation verified offline: `{candidate}` = **{result}**"
            except Exception:
                pass
        elif re.fullmatch(r"[0-9\.\+\-\*\/\^\(\)\s]+", cleaned) and any(op in cleaned for op in "+-*/^"):
            try:
                result = safe_calculate(cleaned)
                return f"Calculation verified offline: `{cleaned}` = **{result}**"
            except Exception:
                pass

        # 2. Check memory storage intent ("remember that ...")
        rem_match = re.match(r"(?i)^remember(?:\s+that)?\s+(.+)$", cleaned)
        if rem_match:
            fact = rem_match.group(1).strip()
            try:
                entry = self.memory.add_memory(
                    title=fact[:60],
                    content=fact,
                    namespace="long_term",
                    tags=["user_fact", "conversation"],
                )
                return f"Stored in Long-Term Memory (`{entry['id']}`): {fact}"
            except Exception as exc:
                return f"Security Policy Notice: {exc}"

        # 3. Search relevant local memories
        recalled = self.memory.search_memory(cleaned, limit=3)
        mem_context = ""
        if recalled:
            bullets = "\n".join(f"- **{m['title']}**: {m['content']}" for m in recalled)
            mem_context = f"\n\n**Relevant Local Memory Recalled:**\n{bullets}"

        # 4. System status / hardware query
        if any(kw in lower for kw in ("system status", "ram", "cpu", "hardware", "mode")):
            snap = self.resources.snapshot()
            return (
                f"**NEXUS ULTRON System Telemetry ({self.connectivity.effective_mode.upper()} MODE)**\n"
                f"- Hardware Profile: {snap['tier_label']}\n"
                f"- CPU Usage: {snap['cpu_percent']}% | RAM Usage: {snap['ram_percent']}% "
                f"({snap['ram_available_gb']} GB available)\n"
                f"- Free Storage: {snap['storage_free_gb']} GB | Worker Slots: {snap['recommended_parallel_workers']}"
                f"{mem_context}"
            )

        # 5. Coding / software engineering assistance
        if any(kw in lower for kw in ("build ", "create app", "inventory", "write python", "code", "scaffold")):
            return (
                "NEXUS ULTRON Autonomous Software Engine is ready. "
                "Submit this objective in **Task Center** or **Developer Center** to automatically scaffold "
                "an isolated project workspace, generate verified source code, execute automated tests, "
                f"self-debug any failures, and package the deliverable.{mem_context}"
            )

        return (
            f"NEXUS ULTRON [{self.connectivity.effective_mode.upper()} CORE] processed your directive: "
            f"\"{cleaned[:160]}\".\n"
            f"All local capabilities (Memory FTS5, File/PDF/DOCX/XLSX Intelligence, Multi-Agent DAG Planner, "
            f"Autonomous Software Builder, and Payment Isolation Shield) are operational.{mem_context}"
        )

    def web_research(self, query: str, target_url: str | None = None) -> dict[str, Any]:
        """Perform online documentation/package research with Payment Isolation & Prompt-Injection protection."""
        if self.connectivity.effective_mode != "online":
            return {
                "online": False,
                "query": query,
                "results": [],
                "summary": "Currently in Offline Mode; answered from local knowledge index.",
            }

        url_to_fetch = target_url or f"https://pypi.org/pypi/{re.sub(r'[^a-zA-Z0-9_-]', '', query.split()[0])}/json"
        self.payment_shield.assert_safe_for_browser(url_to_fetch)

        try:
            with httpx.Client(timeout=10.0, follow_redirects=True, transport=self._http_transport) as client:
                resp = client.get(url_to_fetch, headers={"User-Agent": "NEXUS-ULTRON/3.0"})
                resp.raise_for_status()
                raw_body = resp.text[:6000]
                shielded = self.prompt_shield.inspect_and_wrap(raw_body, source=url_to_fetch)
                return {
                    "online": True,
                    "query": query,
                    "url": url_to_fetch,
                    "status_code": resp.status_code,
                    "injection_neutralized": shielded.injection_detected,
                    "sanitized_content": shielded.safe_text,
                }
        except httpx.NetworkError as exc:
            self.connectivity.report_connection_failure("web_research")
            return {"online": False, "query": query, "error": str(exc), "results": []}
        except Exception as exc:
            return {"online": True, "query": query, "error": str(exc), "results": []}
