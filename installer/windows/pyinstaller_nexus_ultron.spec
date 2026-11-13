# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller Specification for Standalone Windows 10 x64 NEXUS-ULTRON.exe.

IMPORTANT: This spec must ONLY be executed on Windows. Linux Qt shim stubs
(.so files in .venv/qt_shims/) must never be included in the Windows build.
"""

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent

# Explicitly exclude Linux-specific Qt shim stubs and virtualenv from Windows binaries.
# These .so files are Linux-only and must never ship as Windows dependencies.
WINDOWS_EXCLUDE_PATTERNS = [
    ".venv",
    "qt_shims",
    "__pycache__",
]

def _is_excluded(path: str) -> bool:
    parts = Path(path).parts
    return any(exc in parts for exc in WINDOWS_EXCLUDE_PATTERNS)

a = Analysis(
    [str(ROOT / "run_ultron.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "config"), "config"),
        (str(ROOT / "migrations"), "migrations"),
        (str(ROOT / "assets"), "assets"),
        (str(ROOT / "nexus_ultron" / "desktop_ui"), "nexus_ultron/desktop_ui"),
        (str(ROOT / "nexus_ultron" / "web_ui" / "static"), "nexus_ultron/web_ui/static"),
    ],
    hiddenimports=[
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "keyring.backends.Windows",
        "uvicorn.logging",
        "uvicorn.protocols.http.auto",
        "pywinauto",
        "pywinauto.application",
        "pywinauto.findwindows",
        "pywinauto.mouse",
        "pywinauto.keyboard",
        "pywin32",
        "win32com",
        "comtypes",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "scipy", "torch", "tensorflow"] + WINDOWS_EXCLUDE_PATTERNS,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NEXUS-ULTRON",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "assets" / "branding" / "nexus_ultron.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="NEXUS-ULTRON",
)
