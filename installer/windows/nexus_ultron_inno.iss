; NEXUS ULTRON v3.0.0 — Inno Setup Windows 10 (64-bit) Installer Script
[Setup]
AppId={{8F9C4E12-3D51-49A1-9E42-NEXUSULTRONV3}
AppName=NEXUS ULTRON
AppVersion=3.0.0
AppPublisher=NEXUS ULTRON Autonomous Engineering
DefaultDirName={localappdata}\NEXUS-ULTRON
DefaultGroupName=NEXUS ULTRON
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.10240
SetupIconFile=..\..\assets\branding\nexus_ultron.ico
OutputDir=..\..\releases
OutputBaseFilename=NEXUS-ULTRON-v3.0.0-Windows10-x64-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest

[Files]
Source: "..\..\nexus_ultron\*"; DestDir: "{app}\nexus_ultron"; Flags: ignoreversion recursesubdirs
Source: "..\..\config\*"; DestDir: "{app}\config"; Flags: ignoreversion recursesubdirs
Source: "..\..\migrations\*"; DestDir: "{app}\migrations"; Flags: ignoreversion recursesubdirs
Source: "..\..\assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs
Source: "..\..\installer\*"; DestDir: "{app}\installer"; Flags: ignoreversion recursesubdirs
Source: "..\..\run_ultron.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\NexusUltron.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\requirements.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userdesktop}\NEXUS ULTRON"; Filename: "{app}\NexusUltron.bat"; IconFilename: "{app}\assets\branding\nexus_ultron.ico"
Name: "{group}\NEXUS ULTRON"; Filename: "{app}\NexusUltron.bat"; IconFilename: "{app}\assets\branding\nexus_ultron.ico"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\installer\windows\NexusUltronSetup.ps1"" -InstallDir ""{app}"" -Silent"; StatusMsg: "Configuring NEXUS ULTRON runtime, database & health check..."
Filename: "{app}\NexusUltron.bat"; Description: "Launch NEXUS ULTRON now"; Flags: nowait postinstall skipifsilent
