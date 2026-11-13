#!/usr/bin/env python3
"""Builds the Windows One-Click Installer Bundle, Portable Edition & SHA-256 Manifest in releases/."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from installer.lifecycle_manager import LifecycleManager  # noqa: E402
from nexus_ultron.version import __version__  # noqa: E402


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_all_releases() -> dict[str, str]:
    releases_dir = ROOT / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build Windows One-Click Installer Package (Zero-CLI double-click Install-NexusUltron.bat + PowerShell/NSIS/Inno)
    installer_zip = releases_dir / f"NEXUS-ULTRON-v{__version__}-Windows10-x64-Installer.zip"
    include_items = [
        "nexus_ultron",
        "config",
        "migrations",
        "assets",
        "installer",
        "docs",
        "run_ultron.py",
        "NexusUltron.bat",
        "requirements.txt",
        "requirements-windows.txt",
        "pyproject.toml",
        "README.md",
    ]
    # Explicitly exclude Linux-specific Qt shim stubs and virtualenv from Windows builds.
    # These .so files are Linux-only and must never ship as Windows dependencies.
    WINDOWS_EXCLUDE_PARTS = {".venv", "qt_shims", "__pycache__"}
    with zipfile.ZipFile(installer_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # Place a top-level One-Click Setup.bat at the archive root for effortless user experience
        zf.writestr(
            "Setup-NexusUltron.bat",
            "@echo off\r\ncall \"%~dp0installer\\windows\\Install-NexusUltron.bat\" %*\r\n",
        )
        for rel in include_items:
            p = ROOT / rel
            if not p.exists():
                continue
            if p.is_file():
                zf.write(p, p.name)
            else:
                for sub in p.rglob("*"):
                    if sub.is_file() and not any(part in WINDOWS_EXCLUDE_PARTS for part in sub.parts):
                        zf.write(sub, sub.relative_to(ROOT))

    # 2. Build Pre-Initialized Portable Edition (pre-migrated portable_data SQLite DB + settings)
    portable_stage = releases_dir / "_portable_stage"
    if portable_stage.exists():
        import shutil
        shutil.rmtree(portable_stage)

    lm = LifecycleManager(ROOT)
    lm.install(portable_stage, portable_mode=True, simulated_ram_gb=8.0)

    portable_zip = releases_dir / f"NEXUS-ULTRON-v{__version__}-Windows10-x64-Portable.zip"
    with zipfile.ZipFile(portable_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for sub in portable_stage.rglob("*"):
            if sub.is_file() and "__pycache__" not in sub.parts:
                zf.write(sub, f"NEXUS-ULTRON-Portable/{sub.relative_to(portable_stage)}")

    import shutil
    shutil.rmtree(portable_stage)

    # 3. Build Official Brand Identity Asset Kit Archive
    brand_zip = releases_dir / f"NEXUS-ULTRON-v{__version__}-Brand-Identity-Kit.zip"
    with zipfile.ZipFile(brand_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for asset in sorted((ROOT / "assets" / "branding").glob("*")):
            if asset.is_file():
                zf.write(asset, asset.name)

    # 4. Write Cryptographic Checksums Manifest
    manifest = {
        "product": "NEXUS ULTRON",
        "version": __version__,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            p.name: {"size_bytes": p.stat().st_size, "sha256": sha256_file(p)}
            for p in sorted(releases_dir.glob("*.zip"))
        },
    }
    manifest_path = releases_dir / "SHA256SUMS.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {k: v["sha256"] for k, v in manifest["artifacts"].items()}


if __name__ == "__main__":
    built = build_all_releases()
    print(json.dumps(built, indent=2))
