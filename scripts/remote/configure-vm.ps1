# Phase 2: rewrite config (via configure.py), create BOOT-TIME Core service (LocalSystem auto),
# set service env for the debian mesh peer token, start the service. NOT ONLOGON.
$ErrorActionPreference = 'Continue'
$H   = 'http://192.168.122.1:18090'
$CAP = 'http://192.168.122.1:9011'
$py  = 'C:\Python312\python.exe'
$cfgPath = 'C:\ProgramData\AgentNode\config.yaml'
$log = @()
function note($m) { $log += $m; Write-Host $m }
function postup($s, $t) { try { curl.exe -s -X POST --data-binary "STAGE[$s]`r`n$t" ($CAP + '/up') | Out-Null } catch {} }

note ("CONFIGURE-BEGIN " + (Get-Date -Format s))
if (-not (Test-Path $cfgPath)) { note 'CONFIG MISSING'; postup 'cfg-fail' $log; exit 1 }

# 1) rewrite config on the guest with our python
note 'STEP cfg: downloading configure.py'
Invoke-WebRequest ($H + '/scripts/remote/configure.py') -OutFile 'C:\configure.py' -UseBasicParsing
$o = & $py 'C:\configure.py' 2>&1
note (($o | Select-Object -Last 5) -join ' | ')
postup 'cfg' $log

# 2) create boot-time service AgentNodeCore
$runnerPy = @'
import subprocess, sys
cmd = [r'C:\Python312\python.exe', '-m', 'agentnode', 'serve', '--config', r'C:\ProgramData\AgentNode\config.yaml']
logf = open(r'C:\ProgramData\AgentNode\serve.log', 'ab', 0)
p = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
sys.exit(p.wait())
'@
Set-Content -Path 'C:\ProgramData\AgentNode\run_core.py' -Value $runnerPy -Encoding ascii
note 'STEP svc: creating AgentNodeCore'
sc.exe delete AgentNodeCore 2>$null | Out-Null
$bin = '"' + $py + '" "C:\ProgramData\AgentNode\run_core.py"'
sc.exe create AgentNodeCore binPath= $bin start= auto obj= LocalSystem DisplayName= "AgentNode Core" 2>&1 | ForEach-Object { note ($_ -join ' ') }
sc.exe description AgentNodeCore "AgentNode 3.2 core service (boot-time, LocalSystem; mesh reachable without any user logon)" 2>$null | Out-Null
# service failure recovery: restart after 5s up to 3 times
sc.exe failure AgentNodeCore reset= 86400 actions= restart/5000/restart/5000/restart/5000 2>$null | Out-Null
note ('STEP svc: start=' + ((Get-Service AgentNodeCore -ErrorAction SilentlyContinue).StartType))
note ('STEP svc: status=' + ((Get-Service AgentNodeCore -ErrorAction SilentlyContinue).Status))
postup 'svc' $log

# 3) service Environment var for mesh peer token (debian node raw token)
$peerTok = '6c72c38ef21d98d69a5055c7f3b32ea9'
$svcKey = 'HKLM:\SYSTEM\CurrentControlSet\Services\AgentNodeCore'
New-Item -Path $svcKey -Name 'Environment' -Force -ErrorAction SilentlyContinue | Out-Null
if (-not (Get-ItemProperty -Path $svcKey -Name Environment -ErrorAction SilentlyContinue)) {
    New-ItemProperty -Path $svcKey -Name Environment -PropertyType MultiString -Value "AGENTNODE_PEER_DEBIAN_TOKEN=$peerTok" -Force | Out-Null
} else {
    Set-ItemProperty -Path $svcKey -Name Environment -Value (Get-ItemProperty -Path $svcKey -Name Environment).Environment + "`nAGENTNODE_PEER_DEBIAN_TOKEN=$peerTok" -ErrorAction SilentlyContinue | Out-Null
}
postup 'svc-env' $log

# 4) start service now (test before reboot)
note 'STEP svc: starting now'
sc.exe start AgentNodeCore 2>&1 | ForEach-Object { note ($_ -join ' ') }
Start-Sleep -Seconds 6
note ('STEP svc: after start status=' + ((Get-Service AgentNodeCore -ErrorAction SilentlyContinue).Status))
note 'STEP svc: local health check:'
note ((Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -UseBasicParsing -TimeoutSec 10).Content)
note ('STEP svc: listen 8765 => ' + ((netstat -ano | Select-String ':8765').Count -gt 0))
postup 'svc-start' $log
note ("CONFIGURE-END " + (Get-Date -Format s))
