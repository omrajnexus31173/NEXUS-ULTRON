; NEXUS ULTRON v3.0.0 — NSIS Professional Windows 10 (64-bit) Installer Script
!include "MUI2.nsh"
!include "x64.nsh"

Name "NEXUS ULTRON"
OutFile "..\..\releases\NEXUS-ULTRON-v3.0.0-Setup-x64.exe"
InstallDir "$LOCALAPPDATA\NEXUS-ULTRON"
RequestExecutionLevel user

!define MUI_ICON "..\..\assets\branding\nexus_ultron.ico"
!define MUI_UNICON "..\..\assets\branding\nexus_ultron.ico"
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\NexusUltron.bat"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "NEXUS ULTRON requires 64-bit Windows 10 or newer."
    Abort
  ${EndIf}
FunctionEnd

Section "NEXUS ULTRON Core System" SecCore
  SetOutPath "$INSTDIR"
  File /r "..\..\nexus_ultron"
  File /r "..\..\config"
  File /r "..\..\migrations"
  File /r "..\..\assets"
  File /r "..\..\installer"
  File "..\..\run_ultron.py"
  File "..\..\NexusUltron.bat"
  File "..\..\requirements.txt"
  File "..\..\pyproject.toml"

  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\installer\windows\NexusUltronSetup.ps1" -InstallDir "$INSTDIR" -Silent'
  WriteUninstaller "$INSTDIR\Uninstall-NexusUltron.exe"
SectionEnd

Section "Uninstall"
  MessageBox MB_YESNO|MB_ICONQUESTION "Keep your NEXUS ULTRON memories, workspaces, and encrypted vault for future reinstallation?$\n$\nClick YES to retain user_data, or NO to remove everything." IDYES RetainData IDNO WipeAll

  RetainData:
    RMDir /r "$INSTDIR\nexus_ultron"
    RMDir /r "$INSTDIR\config"
    RMDir /r "$INSTDIR\migrations"
    RMDir /r "$INSTDIR\assets"
    RMDir /r "$INSTDIR\.venv"
    RMDir /r "$INSTDIR\runtime"
    Delete "$INSTDIR\run_ultron.py"
    Delete "$INSTDIR\NexusUltron.bat"
    Delete "$DESKTOP\NEXUS ULTRON.lnk"
    Goto DoneUninstall

  WipeAll:
    RMDir /r "$INSTDIR"
    Delete "$DESKTOP\NEXUS ULTRON.lnk"

  DoneUninstall:
SectionEnd
