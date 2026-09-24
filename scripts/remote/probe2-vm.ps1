$ErrorActionPreference='Continue'
$rows=@()
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p  = New-Object Security.Principal.WindowsPrincipal($id)
$rows += "ELEVATED: " + $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$rows += "SESSION: " + (Get-Process -Id $PID).SessionId
try { $s=(Invoke-WebRequest 'https://www.python.org/' -UseBasicParsing -TimeoutSec 15).StatusCode; $rows += "INTERNET-PYTHONORG: $s" } catch { $rows += "INTERNET-PYTHONORG: FAIL $($_.Exception.Message)" }
try { $s=(Invoke-WebRequest 'https://pypi.org/simple/' -UseBasicParsing -TimeoutSec 15).StatusCode; $rows += "INTERNET-PYPI: $s" } catch { $rows += "INTERNET-PYPI: FAIL $($_.Exception.Message)" }
$rows += "RAM-GB: " + [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
$rows += "DISK-FREE-GB: " + [math]::Round((Get-PSDrive C).Free/1GB,1)
$rows += "UPTIME: " + ((Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToString('s'))
$body = ($rows -join "`r`n")
$body | Out-File 'C:\agentnode-probe2.txt' -Encoding utf8
try { curl.exe -s -X POST --data-binary "PROBE2-VM:`r`n$body" http://192.168.122.1:9011/probe2 } catch {}
