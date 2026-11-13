@echo off
TITLE NEXUS ULTRON — One-Click Updater
ECHO [NEXUS ULTRON] Backing up user data and applying latest NEXUS ULTRON update...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NexusUltronSetup.ps1" -Mode install -Silent
ECHO [SUCCESS] NEXUS ULTRON updated cleanly!
PAUSE
