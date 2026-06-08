$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendPort = 8000
$BackendUrl = "http://127.0.0.1:$BackendPort"
$HealthUrl = "$BackendUrl/health"
$BackendProcess = $null
$LogDir = Join-Path $Root "logs"
$StartupLog = Join-Path $LogDir "startup.log"
$BackendOutLog = Join-Path $LogDir "backend.out.log"
$BackendErrLog = Join-Path $LogDir "backend.err.log"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

try {
    Start-Transcript -Path $StartupLog -Append | Out-Null
} catch {
    Write-Host "Warning: cannot start transcript: $($_.Exception.Message)"
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-BackendHealth {
    try {
        return Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3
    } catch {
        return $null
    }
}

function Get-PortOwner {
    $connection = Get-NetTCPConnection -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) {
        return $null
    }
    return Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)" -ErrorAction SilentlyContinue
}

function Stop-StaleBackendIfNeeded {
    $health = Get-BackendHealth
    if ($health -and $health.status -eq "ok" -and $health.build) {
        Write-Host "Backend already running: $HealthUrl"
        Write-Host "Build: $($health.build)"
        return $true
    }

    $owner = Get-PortOwner
    if (-not $owner) {
        return $false
    }

    $commandLine = [string]$owner.CommandLine
    $isThisBackend = $commandLine.Contains("uvicorn") -and $commandLine.Contains("bid_parser_api:app")
    if ($isThisBackend) {
        Write-Host "Stopping stale backend process PID $($owner.ProcessId) ..."
        Stop-Process -Id $owner.ProcessId -Force
        Start-Sleep -Seconds 1
        return $false
    }

    throw "Port $BackendPort is occupied by another process. PID=$($owner.ProcessId), CommandLine=$commandLine"
}

function Wait-BackendReady {
    param([int]$TimeoutSeconds = 45)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $health = Get-BackendHealth
        if ($health -and $health.status -eq "ok") {
            Write-Host "Backend health check passed: $HealthUrl"
            if ($health.build) {
                Write-Host "Build: $($health.build)"
            }
            return
        }
        Start-Sleep -Milliseconds 700
    }

    throw "Backend startup timed out. Run manually from project root: python -m uvicorn bid_parser_api:app --host 127.0.0.1 --port 8000"
}

try {
    Write-Step "Checking project directory"
    Write-Host "Root: $Root"
    Write-Host "Startup log: $StartupLog"
    Write-Host "Backend stdout log: $BackendOutLog"
    Write-Host "Backend stderr log: $BackendErrLog"
    if (-not (Test-Path (Join-Path $Root "bid_parser_api.py"))) {
        throw "Cannot find bid_parser_api.py. Root=$Root"
    }
    if (-not (Test-Path (Join-Path $Root "electron_client\package.json"))) {
        throw "Cannot find electron_client\package.json."
    }

    Write-Step "Checking backend port"
    $backendAlreadyRunning = Stop-StaleBackendIfNeeded

    if (-not $backendAlreadyRunning) {
        Write-Step "Starting FastAPI backend"
        $startInfo = @{
            FilePath = "python"
            ArgumentList = @("-m", "uvicorn", "bid_parser_api:app", "--host", "127.0.0.1", "--port", [string]$BackendPort)
            WorkingDirectory = $Root
            WindowStyle = "Hidden"
            RedirectStandardOutput = $BackendOutLog
            RedirectStandardError = $BackendErrLog
            PassThru = $true
        }
        $BackendProcess = Start-Process @startInfo

        Wait-BackendReady -TimeoutSeconds 45
    }

    Write-Step "Starting Electron frontend"
    $ElectronDir = Join-Path $Root "electron_client"
    if (-not (Test-Path (Join-Path $ElectronDir "node_modules"))) {
        Write-Host "node_modules not found. Running npm.cmd install ..."
        Push-Location $ElectronDir
        try {
            npm.cmd install
        } finally {
            Pop-Location
        }
    }

    Push-Location $ElectronDir
    try {
        npm.cmd start
    } finally {
        Pop-Location
    }
} catch {
    Write-Host ""
    Write-Host "Startup failed:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
} finally {
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Write-Step "Stopping backend started by this script"
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    try {
        Stop-Transcript | Out-Null
    } catch {
    }
}
