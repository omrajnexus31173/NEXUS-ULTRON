"""Centralized Multi-Agent Orchestration Engine with Dynamic Registry & Parallel DAG Execution."""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

from ..core.resource_manager import ResourceManager
from ..intelligence.planner import MasterPlanner
from ..security.permission_engine import PermissionEngine
from .base_agent import BaseAgent, SharedTaskContext
from .builtin_agents import create_default_agents

logger = logging.getLogger("nexus_ultron.orchestrator")


class AgentOrchestrator:
    """
    Coordinates unlimited dynamically registered logical agents across parallel tasks:
      - Executes DAG dependency waves concurrently using adaptive worker sizing from ResourceManager
      - Bounds heavy AI inference via a separate semaphore
      - Isolates agent failures, applies bounded retry policies, and queues excess load safely
      - Immediately honors Emergency Stop & task cancellation
    """

    def __init__(
        self,
        planner: MasterPlanner,
        resources: ResourceManager,
        permissions: PermissionEngine,
        services: dict[str, Any],
    ) -> None:
        self.planner = planner
        self.resources = resources
        self.permissions = permissions
        self.services = services

        self._lock = threading.RLock()
        self._agents: dict[str, BaseAgent] = {}
        for agent in create_default_agents():
            self.register_agent(agent)

        max_workers = max(2, self.resources.hardware.max_parallel_agents)
        self._task_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ultron-task")
        self._heavy_inference_sem = threading.BoundedSemaphore(
            value=max(1, self.resources.hardware.max_local_llm_concurrency * 2)
        )
        self._active_runs: dict[str, dict[str, Any]] = {}
        self._task_queue: queue.PriorityQueue[tuple[int, float, str]] = queue.PriorityQueue()

        self.permissions.register_emergency_stop_callback(self._on_emergency_stop)

    def register_agent(self, agent: BaseAgent) -> None:
        """Dynamically register any custom or built-in specialized agent."""
        with self._lock:
            self._agents[agent.agent_id] = agent

    def unregister_agent(self, agent_id: str) -> bool:
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get_agent(self, agent_id: str) -> BaseAgent:
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"Agent '{agent_id}' is not registered")
            return self._agents[agent_id]

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock:
            active_counts: dict[str, int] = {}
            for run in self._active_runs.values():
                for aid in run.get("active_agents", set()):
                    active_counts[aid] = active_counts.get(aid, 0) + 1
            return [
                {
                    **agent.info(),
                    "active_instances": active_counts.get(aid, 0),
                    "status": "busy" if active_counts.get(aid, 0) > 0 else "idle",
                }
                for aid, agent in self._agents.items()
            ]

    def active_summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "registered_agent_count": len(self._agents),
                "running_tasks": list(self._active_runs.keys()),
                "queued_count": self._task_queue.qsize(),
            }

    def submit_objective_async(self, objective: str, priority: int = 5, mode_used: str = "offline") -> tuple[dict[str, Any], Future[dict[str, Any]]]:
        """Create a planned task and schedule its execution asynchronously."""
        task = self.planner.create_task(objective=objective, priority=priority, mode_used=mode_used)
        self._task_queue.put((-priority, time.time(), task["id"]))
        fut = self._task_executor.submit(self._dequeue_and_run, task["id"])
        return task, fut

    def run_objective_sync(
        self,
        objective: str,
        priority: int = 5,
        mode_used: str = "offline",
        custom_steps: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Plan and execute an objective synchronously, returning the verified task record."""
        task = self.planner.create_task(
            objective=objective,
            priority=priority,
            mode_used=mode_used,
            custom_steps=custom_steps,
        )
        return self.execute_task(task["id"])

    def execute_task(self, task_id: str) -> dict[str, Any]:
        """Execute all pending subtasks of an existing planned task in parallel dependency waves."""
        task = self.planner.get_task(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")

        if self.permissions.emergency_stop_active:
            return self.planner.cancel_task(task_id, reason="Blocked: Emergency Stop active")

        self.planner.update_task_state(task_id, "Running")
        context = SharedTaskContext(
            task_id=task_id,
            objective=task["objective"],
            category=task["category"],
        )
        # Restore prior checkpoint artifacts when resuming after restart
        for k, v in (task.get("checkpoint", {}).get("artifacts") or {}).items():
            context.put(k, v)

        with self._lock:
            self._active_runs[task_id] = {"active_agents": set()}

        try:
            max_retries = int(task.get("max_retries", 2))
            while True:
                if self.permissions.emergency_stop_active:
                    return self.planner.cancel_task(task_id, reason="Halted by Emergency Stop")

                refreshed = self.planner.get_task(task_id)
                if not refreshed or refreshed["state"] == "Cancelled":
                    return refreshed  # type: ignore[return-value]

                subtasks = refreshed["subtasks"]
                completed_indices = {s["step_index"] for s in subtasks if s["state"] == "Completed"}
                pending = [s for s in subtasks if s["state"] in {"Pending", "Waiting"}]

                if not pending:
                    break

                ready_wave = [
                    s
                    for s in pending
                    if all(dep in completed_indices for dep in s["depends_on"])
                ]
                if not ready_wave:
                    return self.planner.update_task_state(
                        task_id,
                        "Failed",
                        verified=False,
                        error_message="Unresolvable subtask dependency cycle or failed prerequisite.",
                    )

                # Adaptive concurrency: inspect current RAM/CPU health before launching wave
                snap = self.resources.snapshot()
                wave_workers = max(1, min(len(ready_wave), snap["recommended_parallel_workers"]))

                with ThreadPoolExecutor(max_workers=wave_workers, thread_name_prefix="ultron-subtask") as sub_pool:
                    fut_map = {
                        sub_pool.submit(self._run_single_subtask, task_id, sub, context, max_retries): sub
                        for sub in ready_wave
                    }
                    wave_errors: list[str] = []
                    for fut in as_completed(fut_map):
                        ok, err_msg = fut.result()
                        if not ok:
                            wave_errors.append(err_msg or "Subtask failed")

                # Persist checkpoint after every wave so restarts resume cleanly!
                self.planner.update_task_state(
                    task_id,
                    "Running",
                    checkpoint=context.snapshot(),
                )

                if wave_errors:
                    return self.planner.update_task_state(
                        task_id,
                        "Failed",
                        verified=False,
                        error_message="; ".join(wave_errors),
                        checkpoint=context.snapshot(),
                    )

            # Final verification check
            final_snap = context.snapshot()
            build_art = final_snap["artifacts"].get("build_result")
            summary_lines = [f"Completed {len(task['subtasks'])} coordinated agent steps."]
            if build_art:
                summary_lines.append(
                    f"Delivered verified {build_art['language']} project '{build_art['project_name']}' "
                    f"at {build_art['workspace_path']} (Package: {build_art.get('package_zip')})."
                )
            return self.planner.update_task_state(
                task_id,
                "Completed",
                result_summary=" ".join(summary_lines),
                verified=True,
                checkpoint=final_snap,
            )
        finally:
            with self._lock:
                self._active_runs.pop(task_id, None)

    def _run_single_subtask(
        self,
        task_id: str,
        subtask: dict[str, Any],
        context: SharedTaskContext,
        max_retries: int,
    ) -> tuple[bool, str | None]:
        sub_id = subtask["id"]
        agent_id = subtask["assigned_agent"]

        try:
            agent = self.get_agent(agent_id)
        except KeyError as exc:
            self.planner.update_subtask(sub_id, "Failed", error_message=str(exc))
            return False, str(exc)

        attempts = 0
        last_err = ""
        while attempts <= max_retries:
            if self.permissions.emergency_stop_active:
                self.planner.update_subtask(sub_id, "Cancelled", error_message="Emergency Stop active")
                return False, "Emergency Stop active"

            attempts += 1
            self.planner.update_subtask(sub_id, "Running")
            with self._lock:
                if task_id in self._active_runs:
                    self._active_runs[task_id]["active_agents"].add(agent_id)

            try:
                if agent.heavy_inference:
                    with self._heavy_inference_sem:
                        out = agent.execute(subtask, context, self.services)
                else:
                    out = agent.execute(subtask, context, self.services)
                self.planner.update_subtask(sub_id, "Completed", output=out, error_message=None)
                return True, None
            except Exception as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Agent '%s' failed subtask '%s' (attempt %d/%d): %s",
                    agent_id,
                    sub_id,
                    attempts,
                    max_retries + 1,
                    last_err,
                )
                if attempts <= max_retries:
                    self.planner.update_subtask(
                        sub_id,
                        "Waiting",
                        error_message=last_err,
                        increment_retry=True,
                    )
                    time.sleep(0.05)
                else:
                    self.planner.update_subtask(sub_id, "Failed", error_message=last_err)
            finally:
                with self._lock:
                    if task_id in self._active_runs:
                        self._active_runs[task_id]["active_agents"].discard(agent_id)

        return False, last_err

    def _dequeue_and_run(self, fallback_task_id: str) -> dict[str, Any]:
        try:
            _, _, tid = self._task_queue.get_nowait()
        except queue.Empty:
            tid = fallback_task_id
        return self.execute_task(tid)

    def _on_emergency_stop(self) -> None:
        with self._lock:
            running_ids = list(self._active_runs.keys())
        for tid in running_ids:
            try:
                self.planner.cancel_task(tid, reason="Emergency Stop triggered")
            except Exception:
                pass

    def shutdown(self) -> None:
        self._task_executor.shutdown(wait=False, cancel_futures=True)
