"""QA Scenarios #18, #19, #29: Multi-Agent Coordination, Parallel DAG Scheduling & Agent Failure Recovery."""

from __future__ import annotations

import time
from typing import Any

from nexus_ultron.agents.base_agent import BaseAgent, SharedTaskContext
from nexus_ultron.runtime import NexusUltronRuntime


class _FlakyRecoverableAgent(BaseAgent):
    agent_id = "flaky_test_agent"
    display_name = "Flaky Test Agent"
    specialty = "Fails on attempt 1, succeeds on attempt 2"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Simulated transient worker crash")
        context.put("recovered_flag", True)
        return {"recovered_on_attempt": self.calls}


class _AlwaysFailingAgent(BaseAgent):
    agent_id = "always_failing_agent"
    display_name = "Always Failing Agent"
    specialty = "Tests bounded retry termination without infinite loop"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        raise ValueError("Unrecoverable defect")


def test_18_and_19_multi_agent_coordination_and_parallel_scheduling(online_runtime: NexusUltronRuntime) -> None:
    """Tests #18 (12 Specialized Agents + Dynamic Agent Coordination) & #19 (Parallel Simultaneous Tasks)."""
    agents = online_runtime.orchestrator.list_agents()
    assert len(agents) >= 12

    # Submit 3 independent objectives concurrently in parallel
    t0 = time.perf_counter()
    _, f1 = online_runtime.orchestrator.submit_objective_async("Analyze data spreadsheet metrics", priority=9)
    _, f2 = online_runtime.orchestrator.submit_objective_async("Generate document report file", priority=7)
    _, f3 = online_runtime.orchestrator.submit_objective_async("Monitor system CPU and RAM health", priority=5)

    r1, r2, r3 = f1.result(timeout=30), f2.result(timeout=30), f3.result(timeout=30)
    elapsed = time.perf_counter() - t0
    assert elapsed < 25.0
    for r in (r1, r2, r3):
        assert r["state"] == "Completed" and r["verified"] is True


def test_29_recovery_from_agent_failure_and_bounded_retries(offline_runtime: NexusUltronRuntime) -> None:
    """Test #29: Transient agent crash recovers automatically; permanent failure stops cleanly without infinite loops."""
    flaky = _FlakyRecoverableAgent()
    offline_runtime.orchestrator.register_agent(flaky)

    res_ok = offline_runtime.orchestrator.run_objective_sync(
        "Test transient agent failure recovery",
        custom_steps=[
            {"step_index": 0, "title": "Run flaky step", "assigned_agent": "flaky_test_agent", "depends_on": []},
            {"step_index": 1, "title": "QA verify", "assigned_agent": "qa_agent", "depends_on": [0]},
        ],
    )
    assert res_ok["state"] == "Completed" and res_ok["verified"] is True
    assert flaky.calls == 2

    # Permanent failure must terminate after max_retries (never claim completion!)
    offline_runtime.orchestrator.register_agent(_AlwaysFailingAgent())
    res_fail = offline_runtime.orchestrator.run_objective_sync(
        "Test bounded failure isolation",
        custom_steps=[
            {"step_index": 0, "title": "Doomed step", "assigned_agent": "always_failing_agent", "depends_on": []},
        ],
    )
    assert res_fail["state"] == "Failed"
    assert res_fail["verified"] is False
