@echo off
SETLOCAL EnableDelayedExpansion
TITLE NEXUS ULTRON — Autonomous Personal AI Operating System
CD /D "%~dp0"

IF EXIST "%~dp0runtime\python.exe" (
    "%~dp0runtime\python.exe" "%~dp0run_ultron.py" --desktop %*
    EXIT /B %ERRORLEVEL%
)

IF EXIST "%~dp0.venv\Scripts\pythonw.exe" (
    START "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0run_ultron.py" --desktop %*
    EXIT /B 0
)

IF EXIST "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0run_ultron.py" --desktop %*
    EXIT /B %ERRORLEVEL%
)

ECHO [NEXUS ULTRON] First-time runtime setup required. Launching One-Click Windows Installer...
CALL "%~dp0installer\windows\Install-NexusUltron.bat"
ENDLOCAL
