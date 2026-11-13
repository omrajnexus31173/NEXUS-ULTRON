@echo off
TITLE NEXUS ULTRON — Uninstaller
ECHO [NEXUS ULTRON] Starting guided uninstaller (choose whether to retain or remove user data)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NexusUltronSetup.ps1" -Mode uninstall %*
PAUSE
