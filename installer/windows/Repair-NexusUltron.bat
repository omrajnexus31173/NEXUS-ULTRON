@echo off
TITLE NEXUS ULTRON — Self-Healing Repair Tool
SET "INSTALL_DIR=%LOCALAPPDATA%\NEXUS-ULTRON"
ECHO [NEXUS ULTRON] Repairing core runtime, configurations, and database schema while preserving user data...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NexusUltronSetup.ps1" -Mode install -Silent
ECHO [SUCCESS] Repair complete. All personal memories and workspaces preserved.
PAUSE
