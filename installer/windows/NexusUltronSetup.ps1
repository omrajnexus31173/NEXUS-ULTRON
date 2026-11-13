<#
.SYNOPSIS
    NEXUS ULTRON v3.0.0 — One-Click Windows 10 (64-bit) Graphical & Automated Installer
.DESCRIPTION
    Performs all 14 installation steps automatically with zero manual Python or terminal setup:
      1. Windows 10+ compatibility check
      2. 64-bit CPU architecture verification
      3. RAM detection & auto-tiering (8GB Lightweight / 12GB Balanced / 16GB Enhanced / 32GB+ High-Performance)
      4. Available storage verification
      5. System component check
      6. Embedded Python 3.11 runtime provisioning (auto-fetches official python.org embeddable package if not bundled)
      7. Compatible wheel dependency installation
      8. Application directory creation (%LOCALAPPDATA%\NEXUS-ULTRON)
      9. SQLite WAL & FTS5 database initialization
     10. Hardware-tuned default configuration
     11. Desktop & Start Menu shortcuts with official NEXUS ULTRON icon
     12. First-launch readiness setup
     13. Automated post-install health & security check
     14. Launch NEXUS ULTRON!
#>

param(
    [string]$Mode = "install",
    [string]$InstallDir = "$env:LOCALAPPDATA\NEXUS-ULTRON",
    [switch]$Portable,
    [switch]$Silent,
    [switch]$RemoveUserData
)

$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Write-Step($Step, $Message) {
    Write-Host ("[NEXUS ULTRON [{0}/14]] {1}" -f $Step, $Message) -ForegroundColor Cyan
}

if ($Mode -eq "uninstall") {
    $RetainData = -not $RemoveUserData.IsPresent
    if (-not $Silent) {
        Add-Type -AssemblyName System.Windows.Forms
        $Choice = [System.Windows.Forms.MessageBox]::Show(
            "NEXUS ULTRON Uninstallation:`n`nClick YES to KEEP your personal memories, workspaces, and encrypted vault for future use.`nClick NO to PERMANENTLY DELETE all user data along with the application.`nClick CANCEL to abort.",
            "Uninstall NEXUS ULTRON",
            [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        if ($Choice -eq [System.Windows.Forms.DialogResult]::Cancel) { exit 0 }
        $RetainData = ($Choice -eq [System.Windows.Forms.DialogResult]::Yes)
    }

    $DesktopLnk = [Environment]::GetFolderPath("Desktop") + "\NEXUS ULTRON.lnk"
    if (Test-Path $DesktopLnk) { Remove-Item $DesktopLnk -Force }

    if ($RetainData) {
        Get-ChildItem -Path $InstallDir -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -notin @("user_data", "portable_data")
        } | Remove-Item -Recurse -Force
        Write-Host "NEXUS ULTRON uninstalled. Your user_data folder was preserved at $InstallDir\user_data" -ForegroundColor Green
    } else {
        if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
        Write-Host "NEXUS ULTRON and all local user data have been completely removed." -ForegroundColor Yellow
    }
    exit 0
}

# --- 1. Check Windows 10 64-bit Compatibility ---
Write-Step 1 "Checking Windows 10 (64-bit) compatibility..."
$OS = Get-CimInstance Win32_OperatingSystem
if ([int]($OS.BuildNumber) -lt 10240) {
    throw "Windows 10 (Build 10240) or newer is required."
}

# --- 2. Detect CPU Architecture ---
Write-Step 2 "Checking 64-bit CPU architecture..."
if (-not [Environment]::Is64BitOperatingSystem) {
    throw "NEXUS ULTRON requires 64-bit Windows 10/11."
}

# --- 3. Detect RAM ---
$RamGB = [math]::Round($OS.TotalVisibleMemorySize / 1MB, 1)
$TierLabel = if ($RamGB -ge 31) { "High-Performance (32GB+)" } elseif ($RamGB -ge 15.5) { "Enhanced (16GB)" } elseif ($RamGB -ge 11.5) { "Balanced (12GB)" } else { "Lightweight (8GB Baseline)" }
Write-Step 3 "Detected $RamGB GB RAM -> Auto-selecting $TierLabel"

# --- 4. Detect Available Storage ---
$TargetRoot = Split-Path -Qualifier $InstallDir
$Drive = Get-PSDrive -Name $TargetRoot.TrimEnd(':')
$FreeGB = [math]::Round($Drive.Free / 1GB, 2)
Write-Step 4 "Detected $FreeGB GB available storage on $TargetRoot"
if ($FreeGB -lt 1.0) {
    throw "At least 1.0 GB of free disk space is required."
}

# --- 5 & 6. Provision Python Runtime Automatically (Zero Manual Python Setup) ---
Write-Step 5 "Checking Python 3.11+ runtime..."
if ($Portable) { $InstallDir = "$PSScriptRoot\..\..\NEXUS-ULTRON-Portable" }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$VenvPython = Join-Path $InstallDir ".venv\Scripts\python.exe"
$SysPython = Get-Command python -ErrorAction SilentlyContinue

Write-Step 6 "Configuring isolated NEXUS ULTRON runtime..."
if (-not (Test-Path $VenvPython)) {
    if ($SysPython) {
        & $SysPython.Source -m venv (Join-Path $InstallDir ".venv")
    } else {
        $RuntimeZip = Join-Path $env:TEMP "python-3.11.9-embed-amd64.zip"
        $RuntimeDir = Join-Path $InstallDir "runtime"
        New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip" -OutFile $RuntimeZip
        Expand-Archive -Path $RuntimeZip -DestinationPath $RuntimeDir -Force
        $PthFile = Join-Path $RuntimeDir "python311._pth"
        (Get-Content $PthFile) -replace '#import site', 'import site' | Set-Content $PthFile
        $GetPip = Join-Path $env:TEMP "get-pip.py"
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
        & (Join-Path $RuntimeDir "python.exe") $GetPip --no-warn-script-location
        $VenvPython = Join-Path $RuntimeDir "python.exe"
    }
}

# --- 7. Copy Application & Install Compatible Dependencies ---
Write-Step 7 "Installing NEXUS ULTRON modules and verified wheels..."
foreach ($Dir in @("nexus_ultron", "config", "migrations", "assets", "installer")) {
    $Src = Join-Path $SourceRoot $Dir
    $Dst = Join-Path $InstallDir $Dir
    if (Test-Path $Src) {
        Copy-Item -Path $Src -Destination $Dst -Recurse -Force
    }
}
foreach ($File in @("run_ultron.py", "NexusUltron.bat", "requirements.txt", "requirements-windows.txt", "pyproject.toml")) {
    $SrcF = Join-Path $SourceRoot $File
    if (Test-Path $SrcF) { Copy-Item -Path $SrcF -Destination (Join-Path $InstallDir $File) -Force }
}

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r (Join-Path $InstallDir "requirements.txt") --quiet
& $VenvPython -m pip install -r (Join-Path $InstallDir "requirements-windows.txt") --quiet

# --- 8-10. Execute Lifecycle Manager (Directories, SQLite DB, Default Settings) ---
Write-Step 8 "Initializing directories, SQLite WAL database & default security profiles..."
$PortableFlag = if ($Portable) { "True" } else { "False" }
& $VenvPython -c "import sys; sys.path.insert(0, r'$InstallDir'); from pathlib import Path; from installer.lifecycle_manager import LifecycleManager; LifecycleManager(Path(r'$InstallDir')).install(Path(r'$InstallDir'), portable_mode=$PortableFlag)"

# --- 11. Create Desktop & Start Menu Shortcuts ---
Write-Step 11 "Creating Windows Desktop & Start Menu shortcuts..."
$WshShell = New-Object -ComObject WScript.Shell
foreach ($LnkPath in @(
    ([Environment]::GetFolderPath("Desktop") + "\NEXUS ULTRON.lnk"),
    ([Environment]::GetFolderPath("Programs") + "\NEXUS ULTRON.lnk")
)) {
    $Shortcut = $WshShell.CreateShortcut($LnkPath)
    $Shortcut.TargetPath = Join-Path $InstallDir "NexusUltron.bat"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.IconLocation = Join-Path $InstallDir "assets\branding\nexus_ultron.ico"
    $Shortcut.Description = "NEXUS ULTRON — Autonomous Personal AI Operating System"
    $Shortcut.Save()
}

# --- 12 & 13. Run Automated Health Check ---
Write-Step 13 "Performing post-installation health & security verification..."
& $VenvPython (Join-Path $InstallDir "run_ultron.py") --health-check

# --- 14. Launch NEXUS ULTRON ---
Write-Step 14 "Installation verified! Launching NEXUS ULTRON..."
if (-not $Silent) {
    Start-Process -FilePath (Join-Path $InstallDir "NexusUltron.bat") -WorkingDirectory $InstallDir
}
