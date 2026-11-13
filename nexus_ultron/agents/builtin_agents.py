"""All 12 Specialized Built-in NEXUS ULTRON Agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .base_agent import BaseAgent, SharedTaskContext


class MasterPlanningAgent(BaseAgent):
    agent_id = "master_planning_agent"
    display_name = "Master Planning Agent"
    specialty = "Objective interpretation, architecture decomposition, tool & model selection"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        dev_engine = services["dev_engine"]
        resources = services["resources"]
        snap = resources.snapshot()
        plan_meta = dev_engine.analyze_requirements(context.objective)
        context.put("architecture_spec", plan_meta)
        context.add_note(f"Planned under {snap['tier_label']}")
        return {
            "status": "planned",
            "selected_stack": plan_meta["framework"],
            "hardware_tier": snap["tier"],
            "features_identified": plan_meta["features"],
        }


class ResearchAgent(BaseAgent):
    agent_id = "research_agent"
    display_name = "Research Agent"
    specialty = "Offline memory synthesis & online web/documentation retrieval"
    heavy_inference = True

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        ai_router = services["ai_router"]
        memory = services["memory"]
        mem_hits = memory.search_memory(context.objective, limit=5)
        web_info = ai_router.web_research(context.objective)
        context.put("research_findings", {"memory_hits": len(mem_hits), "online": web_info.get("online", False)})
        return {
            "status": "researched",
            "local_memory_matches": len(mem_hits),
            "online_research": web_info,
        }


class CodingAgent(BaseAgent):
    agent_id = "coding_agent"
    display_name = "Coding Agent"
    specialty = "Multi-language project scaffolding, code generation & dependency setup"
    heavy_inference = True

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        dev_engine = services["dev_engine"]
        build_result = dev_engine.build_application(context.objective)
        context.put("build_result", build_result)
        return build_result


class DebuggingAgent(BaseAgent):
    agent_id = "debugging_agent"
    display_name = "Debugging Agent"
    specialty = "Traceback inspection, root-cause isolation & backed-up source repair"
    heavy_inference = True

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        dev_engine = services["dev_engine"]
        build_res = context.get("build_result")
        if build_res and not build_res.get("verified"):
            project_dir = Path(build_res["workspace_path"])
            repair = dev_engine.debug_and_repair(
                project_dir,
                build_res.get("language", "python"),
                str(build_res.get("verification", {}).get("error", "")),
            )
            return {"status": "debugged", **repair}
        return {"status": "clean", "fixes_applied": []}


class TestingAgent(BaseAgent):
    agent_id = "testing_agent"
    display_name = "Testing Agent"
    specialty = "Automated unit, integration & smoke test execution"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        dev_engine = services["dev_engine"]
        build_res = context.get("build_result")
        if build_res:
            ver = dev_engine.verify_and_auto_debug(
                Path(build_res["workspace_path"]),
                build_res.get("language", "python"),
            )
            context.put("test_verification", ver)
            if not ver["verified"]:
                raise RuntimeError(f"Generated software failed verification tests: {ver.get('error', '')}")
            return ver
        return {"verified": True, "note": "No software artifact required test run"}


class BrowserAgent(BaseAgent):
    agent_id = "browser_agent"
    display_name = "Browser Agent"
    specialty = "Isolated Chrome & NEXUS Browser navigation, tab control & safe DOM inspection"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        browser = services["browser"]
        iso = browser.get_chrome_isolation_status()
        context.put("browser_isolation", iso)
        return {"status": "browser_ready", "chrome_isolation": iso}


class FileManagementAgent(BaseAgent):
    agent_id = "file_management_agent"
    display_name = "File Management Agent"
    specialty = "Local file search, TXT/PDF/DOCX processing & workspace organization"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        files = services["file_intel"]
        data_root = services["data_root"]
        notes_dir = Path(data_root) / "documents"
        notes_dir.mkdir(parents=True, exist_ok=True)
        out_file = notes_dir / f"{context.task_id}_report.txt"
        written = files.write_text_file(out_file, f"Objective: {context.objective}\nStatus: Processed by File Management Agent.\n")
        context.put("file_artifact", written["path"])
        return written


class EmailAgent(BaseAgent):
    agent_id = "email_agent"
    display_name = "Email Agent"
    specialty = "Authorized OAuth2 Gmail reading & opt-in non-financial login OTP matching"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        gmail = services["gmail"]
        msgs = gmail.search_messages(max_results=5)
        context.put("email_scan_count", len(msgs))
        return {"authorized_messages_scanned": len(msgs)}


class DataAnalysisAgent(BaseAgent):
    agent_id = "data_analysis_agent"
    display_name = "Data Analysis Agent"
    specialty = "Spreadsheet (XLSX/CSV) creation, statistical aggregation & math modeling"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        files = services["file_intel"]
        data_root = Path(services["data_root"]) / "analytics"
        xlsx_path = data_root / f"{context.task_id}_metrics.xlsx"
        res = files.create_or_analyze_spreadsheet(
            xlsx_path,
            headers=["Item", "Value"],
            rows=[["Baseline", 100], ["Optimized", 145], ["Verified", 190]],
            numeric_column_index=1,
        )
        context.put("analytics_sheet", res)
        return res


class DocumentationAgent(BaseAgent):
    agent_id = "documentation_agent"
    display_name = "Documentation Agent"
    specialty = "Architecture specs, READMEs, API guides & release documentation"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        build_res = context.get("build_result")
        if build_res:
            arch_path = Path(build_res["workspace_path"]) / "ARCHITECTURE.md"
            arch_path.write_text(
                f"# Architecture Specification — {build_res['project_name']}\n\n"
                f"- Language: `{build_res['language']}`\n"
                f"- Framework: `{build_res['framework']}`\n"
                f"- Verified Deliverable: `{build_res['verified']}`\n",
                encoding="utf-8",
            )
            return {"documentation_path": str(arch_path)}
        return {"documentation_status": "inline_summary_prepared"}


class SystemMonitoringAgent(BaseAgent):
    agent_id = "system_monitoring_agent"
    display_name = "System Monitoring Agent"
    specialty = "CPU, RAM, storage, battery, network & worker health telemetry"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        snap = services["resources"].snapshot()
        context.put("telemetry", snap)
        return snap


class QualityAssuranceAgent(BaseAgent):
    agent_id = "qa_agent"
    display_name = "Quality Assurance Agent"
    specialty = "Final deliverable verification gate (blocks unverified completion claims)"

    def execute(self, subtask: dict[str, Any], context: SharedTaskContext, services: dict[str, Any]) -> dict[str, Any]:
        snap = context.snapshot()
        build_res = snap["artifacts"].get("build_result")
        if build_res is not None and not build_res.get("verified", False):
            raise RuntimeError("QA Gate rejected task completion: software build artifact is NOT verified.")
        file_art = snap["artifacts"].get("file_artifact")
        if file_art and not Path(file_art).exists():
            raise RuntimeError(f"QA Gate rejected task completion: expected file {file_art} missing on disk.")
        return {
            "qa_verified": True,
            "artifacts_checked": list(snap["artifacts"].keys()),
        }


def create_default_agents() -> list[BaseAgent]:
    return [
        MasterPlanningAgent(),
        ResearchAgent(),
        CodingAgent(),
        DebuggingAgent(),
        TestingAgent(),
        BrowserAgent(),
        FileManagementAgent(),
        EmailAgent(),
        DataAnalysisAgent(),
        DocumentationAgent(),
        SystemMonitoringAgent(),
        QualityAssuranceAgent(),
    ]
