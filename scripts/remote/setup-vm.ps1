# Phase 1: install real Python, deploy agentnode from local repo, pip install deps, init config.
# Results POSTed to host capture server on 192.168.122.1:9011 (stage markers + token lines + raw config).
$ErrorActionPreference = 'Continue'
$H   = 'http://192.168.122.1:18090'   # host file server (repo zip + scripts)
$CAP = 'http://192.168.122.1:9011'    # host capture server (readback)
$log = @()
function note($m) { $log += $m; Write-Host $m }
function postup($stage, $txt) {
    try { $body = "STAGE[$stage]`r`n" + ($txt -join "`r`n"); curl.exe -s -X POST --data-binary $body ($CAP + '/up') | Out-Null } catch {}
}
$py = 'C:\Python312\python.exe'

note ("SETUP-BEGIN " + (Get-Date -Format s))

# 1) Python 3.12.10 system-wide to C:\Python312
if (-not (Test-Path $py)) {
    note 'STEP python: downloading installer'
    Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile 'C:\py-installer.exe' -UseBasicParsing
    note ('STEP python: bytes=' + (Get-Item 'C:\py-installer.exe').Length)
    $p = Start-Process -FilePath 'C:\py-installer.exe' -ArgumentList '/quiet','InstallAllUsers=1','TargetDir=C:\Python312','Include_pip=1','Include_launcher=0','Include_test=0','Include_doc=0','Shortcuts=0','PrependPath=0' -Wait -PassThru
    note ('STEP python: installer exit=' + $p.ExitCode)
    Start-Sleep -Seconds 4
}
if (Test-Path $py) { note ('STEP python: ver=' + (& $py -V 2>&1)) } else { note 'STEP python: NOT FOUND'; postup 'python-fail' $log; exit 1 }
postup 'python' $log

# 2) deploy repo zip
note 'STEP repo: downloading'
Invoke-WebRequest ($H + '/agentnode-repo.zip') -OutFile 'C:\agentnode-repo.zip' -UseBasicParsing
note ('STEP repo: bytes=' + (Get-Item 'C:\agentnode-repo.zip').Length)
if (Test-Path 'C:\AgentNode') { Remove-Item 'C:\AgentNode' -Recurse -Force }
Expand-Archive -Path 'C:\agentnode-repo.zip' -DestinationPath 'C:\AgentNode' -Force
note ('STEP repo: pyproject=' + (Test-Path 'C:\AgentNode\pyproject.toml') + ' files=' + (Get-ChildItem 'C:\AgentNode' -Recurse -File).Count)
postup 'repo' $log

# 3) pip install agentnode[windows...] from local dir
note 'STEP pip: upgrading pip'
$o = & $py -m pip install --upgrade pip 2>&1
note ('STEP pip: pip now ' + (& $py -m pip --version 2>&1))
note 'STEP pip: installing agentnode[mcp,documents,browser,windows]'
$o = & $py -m pip install 'C:\AgentNode[mcp,documents,browser,windows]' 2>&1
note ('STEP pip: exit=' + $LASTEXITCODE)
note (($o | Select-Object -Last 14) -join " | ")
# verify import
$imp = & $py -c "import agentnode; print('agentnode', agentnode.__version__ if hasattr(agentnode,'__version__') else 'ok', agentnode.__file__)" 2>&1
note ('STEP pip: import=' + ($imp -join ' '))
$cli = & $py -m agentnode --help 2>&1
note ('STEP pip: cli has desktop-worker=' + [bool](($cli | Select-String 'desktop-worker')))
postup 'pip' $log

# 4) init config (capture raw tokens)
note 'STEP init: running agentnode init'
$initDir = 'C:\ProgramData\AgentNode'
if (-not (Test-Path $initDir)) { New-Item -ItemType Directory -Path $initDir -Force | Out-Null }
$cfgPath = Join-Path $initDir 'config.yaml'
$initOut = & $py -m agentnode init --config $cfgPath 2>&1
note (($initOut | Select-Object -First 6) -join " | ")
note ('STEP init: config exists=' + (Test-Path $cfgPath))
# POST raw tokens separately (never written to disk beyond this var)
try { curl.exe -s -X POST --data-binary (($initOut | Where-Object { $_ -match '^(operator|super|node): ' }) -join "`r`n") ($CAP + '/tokens') | Out-Null } catch {}
# POST the whole generated config for host-side review
if (Test-Path $cfgPath) {
    $cfgTxt = Get-Content $cfgPath -Raw
    try { curl.exe -s -X POST --data-binary "CONFIG-BEGIN`r`n$cfgTxt`r`nCONFIG-END" ($CAP + '/cfg') | Out-Null } catch {}
}
note 'STEP init: done'
postup 'init' $log

note ("SETUP-END " + (Get-Date -Format s))
