@echo off
TITLE NEXUS ULTRON — One-Click Windows 10 Installer
ECHO ============================================================================
ECHO   NEXUS ULTRON v3.0.0 — ONE MIND. INFINITE CAPABILITIES.
ECHO   Autonomous Personal AI Operating System — One-Click Windows Setup
ECHO ============================================================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0NexusUltronSetup.ps1" -Mode install %*
IF %ERRORLEVEL% NEQ 0 (
    ECHO [ERROR] Installation encountered an error. Review message above.
    PAUSE
    EXIT /B %ERRORLEVEL%
)
ECHO [SUCCESS] NEXUS ULTRON installed and verified!
