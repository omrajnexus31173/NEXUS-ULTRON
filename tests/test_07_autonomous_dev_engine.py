"""QA Scenarios #20, #21, #22, #23: Software Generation, Execution, Self-Debugging & Automated Testing."""

from __future__ import annotations

from pathlib import Path

from nexus_ultron.runtime import NexusUltronRuntime


def test_20_21_23_end_to_end_inventory_app_and_multilang_builds(offline_runtime: NexusUltronRuntime) -> None:
    """Tests #20 (Software generation), #21 (Software execution) & #23 (Automated testing across Python, JS, C, C++)."""
    # 1. Flagship Core Vision Test: Complete Inventory Management Application
    inv_build = offline_runtime.dev_engine.build_application(
        "Build me a complete inventory management application with authentication, billing, stock management, reporting and an admin dashboard.",
        create_isolated_venv=True,
    )
    assert inv_build["verified"] is True
    assert Path(inv_build["package_zip"]).exists()
    assert "SMOKE VERIFICATION PASSED" in inv_build["verification"]["test_output"]

    # Safeguarding existing workspaces: building again with same name must NOT overwrite without permission!
    inv_build_2 = offline_runtime.dev_engine.build_application(
        "Build me a complete inventory management application with authentication, billing, stock management, reporting and an admin dashboard.",
        project_name=inv_build["project_name"],
        overwrite_existing=False,
    )
    assert inv_build_2["workspace_path"] != inv_build["workspace_path"]

    # 2. Multi-language verification: JavaScript (Node.js), C (GCC), and C++ (G++)
    for lang in ("javascript", "c", "cpp"):
        res = offline_runtime.dev_engine.build_application(f"Build native {lang} verification utility", requested_language=lang)
        assert res["verified"] is True, f"Failed {lang} build: {res}"


def test_22_automated_self_debugging_with_pre_modify_backup(offline_runtime: NexusUltronRuntime, tmp_path: Path) -> None:
    """Test #22: Deliberately broken Python project is backed up and automatically repaired by Debugging Engine."""
    broken_dir = tmp_path / "broken_python_app"
    (broken_dir / "tests").mkdir(parents=True)

    # Deliberate bugs: missing `import json`, missing colon on `def compute()`, and `/ 0` ZeroDivisionError!
    (broken_dir / "main.py").write_text(
        "def compute()\n"
        "    val = 100 / 0\n"
        "    print(json.dumps({'ok': True, 'val': val}))\n\n"
        "if __name__ == '__main__':\n"
        "    compute()\n",
        encoding="utf-8",
    )
    (broken_dir / "tests" / "test_basic.py").write_text(
        "import unittest\nfrom main import compute\n\n"
        "class BasicTest(unittest.TestCase):\n"
        "    def test_runs(self):\n"
        "        compute()\n",
        encoding="utf-8",
    )

    result = offline_runtime.dev_engine.verify_and_auto_debug(broken_dir, "python", max_debug_rounds=3)
    assert result["verified"] is True
    assert result["auto_repaired"] is True
    # Confirm pre-modification backup ZIP was created
    backups = list(offline_runtime.dev_engine.backups_root.glob("broken_python_app_backup_*.zip"))
    assert len(backups) >= 1


def test_c_compiler_detection_and_compilation(offline_runtime: NexusUltronRuntime) -> None:
    """Regression: C compiler discovery works and actual C code compiles + executes.

    On Linux: gcc must be found. On Windows: cl.exe (MSVC) or gcc (MinGW) must be found.
    Verifies the fix for [WinError 2] when no C compiler is configured on Windows CI.
    """
    import shutil
    import sys

    if sys.platform == "win32":
        expected = shutil.which("cl.exe") or shutil.which("gcc")
        assert expected is not None, "Windows CI must have cl.exe (MSVC) or gcc (MinGW) on PATH"
    else:
        expected = shutil.which("gcc")
        assert expected is not None, "gcc must be installed for C compilation tests"

    res = offline_runtime.dev_engine.build_application("Build native C verification utility", requested_language="c")
    assert res["verified"] is True, f"C build failed: {res}"
    assert "native binary self-test PASSED" in res["verification"]["test_output"]


def test_cpp_compiler_detection_and_compilation(offline_runtime: NexusUltronRuntime) -> None:
    """Regression: C++ compiler discovery works and actual C++ code compiles + executes.

    On Linux: g++ must be found. On Windows: cl.exe (MSVC) or g++ (MinGW) must be found.
    """
    import shutil
    import sys

    if sys.platform == "win32":
        expected = shutil.which("cl.exe") or shutil.which("g++")
        assert expected is not None, "Windows CI must have cl.exe (MSVC) or g++ (MinGW) on PATH"
    else:
        expected = shutil.which("g++")
        assert expected is not None, "g++ must be installed for C++ compilation tests"

    res = offline_runtime.dev_engine.build_application("Build native C++ verification utility", requested_language="cpp")
    assert res["verified"] is True, f"C++ build failed: {res}"
    assert "native binary self-test PASSED" in res["verification"]["test_output"]
