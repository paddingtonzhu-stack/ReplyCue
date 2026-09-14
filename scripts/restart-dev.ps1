[CmdletBinding()]
param(
    [switch]$StopOnly,
    [ValidateRange(5,120)][int]$TimeoutSeconds = 30,
    [switch]$FrontendWorker
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path.TrimEnd('\')
$backendDir = Join-Path $projectRoot 'backend'
$frontendDir = Join-Path $projectRoot 'frontend'
$pythonExe = Join-Path $backendDir '.venv\Scripts\python.exe'
$runtimeDir = Join-Path $projectRoot '.dev-runtime'
$scriptFile = $PSCommandPath

# A persistent worker gives npm's relative-path children a verifiable ancestor.
if ($FrontendWorker) {
    Set-Location -LiteralPath $frontendDir
    & npm.cmd run dev -- --port 5173 --strictPort
    exit $LASTEXITCODE
}

function Get-Processes { @(Get-CimInstance Win32_Process) }
function Is-ServerProcess($process) {
    $command = [string]$process.CommandLine
    return (($process.Name -match '^python(w)?\.exe$' -and $command -match '\buvicorn\s+app\.main:app\b') -or
        ($process.Name -match '^(node|cmd|powershell|pwsh)\.exe$' -and
         $command -match '(\bvite\b|npm(?:-cli\.js|\.cmd)?.*\brun\s+dev\b|restart-dev\.ps1.*-FrontendWorker)'))
}
function Has-ProjectPath($process) {
    $command = ([string]$process.CommandLine).Replace('/', '\')
    return $command.IndexOf($projectRoot + '\', [StringComparison]::OrdinalIgnoreCase) -ge 0
}
function Is-Owned($process, $all) {
    if (-not (Is-ServerProcess $process)) { return $false }
    $seen = @{}
    $current = $process
    while ($null -ne $current -and -not $seen.ContainsKey([int]$current.ProcessId)) {
        $seen[[int]$current.ProcessId] = $true
        if ((Is-ServerProcess $current) -and (Has-ProjectPath $current)) { return $true }
        $parent = $all | Where-Object { $_.ProcessId -eq $current.ParentProcessId } | Select-Object -First 1
        if ($null -eq $parent -or $parent.CreationDate -gt $current.CreationDate) { break }
        $current = $parent
    }
    return $false
}
function Stop-Verified($processes) {
    # Stop parents first to prevent npm/worker shells launching replacement children.
    foreach ($process in ($processes | Sort-Object CreationDate)) {
        $live = Get-CimInstance Win32_Process -Filter "ProcessId=$($process.ProcessId)"
        if ($null -ne $live -and $live.CreationDate -eq $process.CreationDate -and
            $live.CommandLine -eq $process.CommandLine) {
            Stop-Process -Id $live.ProcessId -Force
        }
    }
}
function Get-Listeners { @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue) }
function Wait-Ready($url, $backend) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                if ($backend) {
                    if (($response.Content | ConvertFrom-Json).status -eq 'ok') { return }
                } elseif ($response.Content -match 'ReplyCue') { return }
            }
        } catch { }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $deadline)
    throw "Server did not become ready at $url within $TimeoutSeconds seconds."
}

if (-not $StopOnly) {
    if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Backend environment missing. In backend, create .venv and install requirements.txt first.' }
    & $pythonExe -c 'import fastapi, uvicorn, multipart, tzdata' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependencies missing. Run backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt.' }
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue) -or -not (Get-Command node.exe -ErrorAction SilentlyContinue)) {
        throw 'Node.js/npm are missing from PATH. Install a supported Node.js version, then reopen PowerShell.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $frontendDir 'node_modules\vite\bin\vite.js'))) { throw 'Frontend dependencies missing. Run npm install in frontend first.' }
}

$all = Get-Processes
$owned = @($all | Where-Object { Is-Owned $_ $all })
$listeners = Get-Listeners
# Check all required ports before stopping anything. Unrelated fallback ports are preserved.
foreach ($listener in ($listeners | Where-Object { $_.LocalPort -in 8000,5173 })) {
    if ($listener.OwningProcess -notin @($owned | ForEach-Object { $_.ProcessId })) {
        throw "Port $($listener.LocalPort) belongs to PID $($listener.OwningProcess), which cannot be verified as this ReplyCue checkout. Stop it manually in its original terminal; nothing was stopped."
    }
}
Stop-Verified $owned
if ($StopOnly) { Write-Host 'Verified ReplyCue development servers stopped.'; exit 0 }

$deadline = (Get-Date).AddSeconds(5)
while (@(Get-Listeners | Where-Object { $_.LocalPort -in 8000,5173 }).Count -gt 0) {
    if ((Get-Date) -gt $deadline) { throw 'Ports are still occupied after shutdown. No new servers were launched.' }
    Start-Sleep -Milliseconds 200
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
$backendOut = Join-Path $runtimeDir 'backend.log'
$backendError = Join-Path $runtimeDir 'backend-error.log'
$frontendOut = Join-Path $runtimeDir 'frontend.log'
$frontendError = Join-Path $runtimeDir 'frontend-error.log'
$started = @()
try {
    $backendProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log' -WorkingDirectory $backendDir -WindowStyle Hidden -RedirectStandardOutput $backendOut -RedirectStandardError $backendError -PassThru
    $started += Get-CimInstance Win32_Process -Filter "ProcessId=$($backendProcess.Id)"
    $workerArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + $scriptFile + '" -FrontendWorker'
    $frontendProcess = Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList $workerArgs -WorkingDirectory $frontendDir -WindowStyle Hidden -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendError -PassThru
    $started += Get-CimInstance Win32_Process -Filter "ProcessId=$($frontendProcess.Id)"
    Wait-Ready 'http://127.0.0.1:8000/health' $true
    Wait-Ready 'http://127.0.0.1:5173/' $false
    $fresh = Get-Processes
    foreach ($listener in (Get-Listeners | Where-Object { $_.LocalPort -in 8000,5173 })) {
        $process = $fresh | Where-Object { $_.ProcessId -eq $listener.OwningProcess } | Select-Object -First 1
        if (-not (Is-Owned $process $fresh)) { throw 'A required port was taken by another process during startup.' }
    }
    Write-Host "Frontend: http://127.0.0.1:5173/"
    Write-Host "Backend:  http://127.0.0.1:8000/health"
    Write-Host "Logs:     $runtimeDir"
} catch {
    $failure = $_
    $fresh = Get-Processes
    $newTree = @($started)
    do {
        $children = @($fresh | Where-Object {
            $_.ProcessId -notin @($newTree | ForEach-Object { $_.ProcessId }) -and
            $_.ParentProcessId -in @($newTree | ForEach-Object { $_.ProcessId }) -and
            (Is-ServerProcess $_) -and (Is-Owned $_ $fresh)
        })
        $newTree += $children
    } while ($children.Count -gt 0)
    Stop-Verified ($newTree | Where-Object { $null -ne $_ })
    # Only emit known startup diagnostics, never arbitrary application/request text.
    foreach ($log in @($backendError,$frontendError,$frontendOut)) {
        if (Test-Path -LiteralPath $log) {
            Get-Content -LiteralPath $log -Tail 15 | Where-Object {
                $_ -match 'address already in use|EADDRINUSE|ModuleNotFoundError|Error loading ASGI|Port .* is already in use|command not found'
            } | ForEach-Object { Write-Warning $_ }
        }
    }
    throw "$($failure.Exception.Message) Startup logs: $runtimeDir"
}
