# NEXUS ULTRON — Developer Extension Guide

**Version:** 3.0.0

---

## 1. Adding a Custom Skill (Plugin)

Skills live in `nexus_ultron/plugins/plugin_manager.py`. A skill is registered with an ID, handler, and permission requirements:

```python
from nexus_ultron.plugins.plugin_manager import PluginManager

# Example: register a skill (via PluginManager API)
# plugin_manager.register_skill(skill_id="my_skill", handler=my_handler, permissions=["local_file_access"])
```

Skills are stored in SQLite, validated against permissions, and executed with fault isolation — a failing skill cannot crash the host.

---

## 2. Adding a Custom Agent

Extend `nexus_ultron/agents/base_agent.py`:

```python
from nexus_ultron.agents.base_agent import BaseAgent, SharedTaskContext

class MyAgent(BaseAgent):
    agent_id = "my_custom_agent"
    display_name = "My Custom Agent"
    specialty = "Custom domain logic"

    def execute(self, subtask, context, services):
        # subtask: {step_index, title, assigned_agent, depends_on}
        # context: SharedTaskContext (put/get shared data)
        # services: runtime services (memory, browser, file_intel, ...)
        return {"result": "done"}
```

Register it with the orchestrator:

```python
runtime.orchestrator.register_agent(MyAgent())
```

Agents support dynamic registration and parallel DAG execution with resource-aware queuing.

---

## 3. Autonomous Software Development

Use `nexus_ultron/developer/dev_engine.py` (`AutonomousDevEngine`):

```python
result = runtime.dev_engine.build_application(
    "Build a task tracker with CLI and JSON storage",
    requested_language="python",
    create_isolated_venv=True,
)
# result: {verified, package_zip, project_name, verification}
```

Supports Python, C, C++, Java, JavaScript, TypeScript, HTML/CSS, SQL. Each build runs in an isolated workspace/venv, is tested, self-debugs on failure (with pre-modification backup), and is packaged as a ZIP.

---

## 4. Extending File Intelligence

`nexus_ultron/intelligence/file_intelligence.py` supports DOCX, XLSX, PDF, TXT. Add new readers/writers by extending the file intelligence class and registering handlers.

---

## 5. Running the Test Suite

```bash
python -m pytest tests/ -q   # 21 tests, covering all 30 scenarios
```

Tests use `tests/conftest.py` fixtures (`offline_runtime`, `online_runtime`, `repo_root`) and auto-heal headless Qt shims on Linux.

---

## 6. Building the Windows Installer

```bash
python installer/build_release.py
```

Produces `releases/` with the Installer ZIP, Portable ZIP, Brand Identity Kit ZIP, and `SHA256SUMS.json`. CI pipeline: `.github/workflows/build-windows-installer.yml`.

---

## 7. Project Layout

```
nexus_ultron/         # core package (runtime + 16 subsystems)
  core/ storage/ security/ intelligence/ automation/
  developer/ agents/ voice/ plugins/ desktop_ui/ web_ui/
installer/            # lifecycle + release builder + Windows specs
tests/                # 30-scenario QA suite
docs/                 # documentation
config/ migrations/ assets/branding/ releases/
run_ultron.py cli.py NexusUltron.bat
```
