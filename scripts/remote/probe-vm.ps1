$ErrorActionPreference='Continue'
$rows=@()
$rows += "WHOAMI: " + (whoami)
$rows += "COMPUTER: " + $env:COMPUTERNAME
$rows += "OS: " + (Get-CimInstance Win32_OperatingSystem).Caption + ' build ' + (Get-CimInstance Win32_OperatingSystem).BuildNumber
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) { $rows += "PYTHON: " + $py.Source + ' :: ' + (& python -V 2>&1) } else { $rows += "PYTHON: none" }
$pyw = Get-Command py -ErrorAction SilentlyContinue
if ($pyw) { $rows += "PY-LAUNCHER: " + $pyw.Source } else { $rows += "PY-LAUNCHER: none" }
if (Test-Path 'C:\Program Files\AgentNode') { $rows += "INSTALLDIR: exists" } else { $rows += "INSTALLDIR: no" }
$an = Get-Command agentnode -ErrorAction SilentlyContinue
if ($an) { $rows += "AGENTNODE: " + $an.Source } else { $rows += "AGENTNODE: none" }
$mod = python -c "import agentnode,sys; print('agentnode import OK', agentnode.__file__)" 2>&1
$rows += "AGENTNODE-MOD: " + ($mod -join ' ')
$svc = Get-Service AgentNode -ErrorAction SilentlyContinue
if ($svc) { $rows += "SVC: " + $svc.Status + ' start=' + $svc.StartType } else { $rows += "SVC: none" }
$rows += "LISTEN-8765:"
$rows += (netstat -ano | Select-String ':8765' | Out-String).Trim()
$rows += "CONFIG:"
$cfg='C:\ProgramData\AgentNode\config.yaml'
if (Test-Path $cfg) { $rows += (Get-Content $cfg -Raw).Substring(0,[Math]::Min(4000,(Get-Content $cfg -Raw).Length)) } else { $rows += 'no config at ' + $cfg }
$rows += "TASKS:"
$rows += (Get-ScheduledTask | Where-Object { $_.TaskName -match 'Agent' } | Select-Object TaskName,State | Out-String)
$rows += "LS-PROG-AGENT:"
if (Test-Path 'C:\Program Files\AgentNode') { $rows += (Get-ChildItem 'C:\Program Files\AgentNode' | Select-Object -First 20 Name | Out-String) }
$body = ($rows -join "`r`n")
$body | Out-File 'C:\agentnode-probe.txt' -Encoding utf8
try { curl.exe -s -X POST --data-binary "PROBE-VM:`r`n$body" http://192.168.122.1:9011/probe } catch {}
