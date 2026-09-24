param(
    [string]$InstallDir = "C:\Program Files\AgentNode",
    [string]$ConfigPath = "C:\ProgramData\AgentNode\config.yaml",
    [string]$AppDir = "C:\ProgramData\AgentNode"
)
# AgentNode 3.2 Windows installer.
#
# Installs TWO pieces:
#   1. AgentNode Core  - a native Windows SERVICE (sc.exe, start= auto) that runs
#      as LocalSystem and starts when the machine boots, independent of any
#      interactive logon. This is what keeps the node reachable after a reboot.
#      A bare "python -m agentnode serve" can NOT be the service binary directly:
#      services start with CWD=C:\Windows\System32 and a stripped PATH, which
#      breaks relative data paths and interpreter resolution. So we install a
#      small run_core.py wrapper that chdir()s to the app directory, loads the
#      operator-editable service.env (mesh peer tokens / PATH overrides), spawns
#      the real server with stdout/err captured to serve.log, and waits as the
#      service main process.
#   2. AgentNode Desktop Worker - an interactive-session worker for UI automation.
#      By design it stays a per-logon task (not a boot service): desktop access
#      requires a logged-in user session, which a Session-0 service does not have.
#      The Core service requires no logon at all.
$ErrorActionPreference = 'Stop'
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]'Administrator')) {
    throw 'Run as Administrator'
}

New-Item -ItemType Directory -Force -Path $InstallDir,$AppDir,(Split-Path $ConfigPath),"$AppDir\data" | Out-Null

$Python = (Get-Command python).Source
if (-not $Python) { $Python = "C:\Python312\python.exe" }
if (-not (Test-Path $ConfigPath)) { & $Python -m agentnode init --config $ConfigPath }

# --- 1. Core boot-time service ------------------------------------------------
$wrapper = @'
import os, subprocess, sys
APP_DIR = r'{APPDIR}'
os.chdir(APP_DIR)
# services inherit a stripped environment; load optional KEY=VALUE overrides
# (mesh peer tokens, PATH additions) from service.env so the operator does not
# need registry edits to configure mesh delegation.
envf = os.path.join(APP_DIR, 'service.env')
if os.path.isfile(envf):
    for line in open(envf, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()
cmd = [sys.executable, '-m', 'agentnode', 'serve', '--config', r'{CONFIG}']
logf = open(os.path.join(APP_DIR, 'serve.log'), 'ab', 0)
p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
sys.exit(p.wait())
'@
$wrapper = $wrapper -replace '{APPDIR}', $AppDir -replace '{CONFIG}', $ConfigPath
Set-Content -Path "$AppDir\run_core.py" -Value $wrapper -Encoding UTF8

# Persist mesh peer tokens / PATH reference for the service. Tokens are only
# written if they were present in the installer's environment.
$envLines = @("PATH=C:\Python312;C:\Windows\System32")
Get-ChildItem Env: | Where-Object { $_.Name -like 'AGENTNODE_*' } | ForEach-Object {
    $envLines += "$($_.Name)=$($_.Value)"
}
Set-Content -Path "$AppDir\service.env" -Value ($envLines -join "`n") -Encoding UTF8

$bin = '"' + $Python + '" "' + "$AppDir\run_core.py" + '"'
sc.exe stop AgentNode 2>$null | Out-Null
sc.exe delete AgentNode 2>$null | Out-Null
sc.exe create AgentNode binPath= $bin start= auto obj= LocalSystem DisplayName= "AgentNode 3.0 Core" | Out-Null
sc.exe failure AgentNode reset= 60 actions= restart/5000/restart/10000/""/0 | Out-Null
sc.exe description AgentNode "Cross-platform AI Agent execution node (boot-time core service)" | Out-Null
sc.exe start AgentNode | Out-Null
Write-Host 'AgentNode Core service installed (start= auto, LocalSystem, boot-time).'

# --- 2. Desktop Worker (interactive-session worker, by design) ----------------
$worker = '"' + $Python + '" -m agentnode desktop-worker --config "' + $ConfigPath + '"'
schtasks.exe /Create /TN "AgentNode Desktop Worker" /SC ONLOGON /RL HIGHEST /TR $worker /F | Out-Null
Write-Host 'Installed AgentNode Core service and Desktop Worker task.'
Write-Host "Configuration: $ConfigPath"
