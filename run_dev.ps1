param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8501,
    [string]$HostAddress = "127.0.0.1",
    [switch]$KeepExisting,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LogsDir = Join-Path $ProjectRoot "logs"
$BackendOutLog = Join-Path $LogsDir "backend.out.log"
$BackendErrLog = Join-Path $LogsDir "backend.err.log"
$FrontendOutLog = Join-Path $LogsDir "frontend.out.log"
$FrontendErrLog = Join-Path $LogsDir "frontend.err.log"

function Assert-CommandReady {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Virtual environment was not found: $VenvPython" -ForegroundColor Red
        Write-Host "Create it first:" -ForegroundColor Yellow
        Write-Host "  python -m venv .venv"
        Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
        exit 1
    }
}

function Test-PortInUse {
    param([int]$Port)
    $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" } |
        Select-Object -First 1
    return $null -ne $connection
}

function Stop-PortProcesses {
    param([int[]]$Ports)

    $processIds = Get-NetTCPConnection -LocalPort $Ports -ErrorAction SilentlyContinue |
        Where-Object { $_.State -eq "Listen" } |
        Select-Object -ExpandProperty OwningProcess -Unique

    foreach ($processId in $processIds) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process) {
            Write-Host "Stopping existing service on target port. PID: $processId ($($process.ProcessName))" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force
        }
    }
}

function Start-ServiceProcess {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$OutLogPath,
        [string]$ErrLogPath
    )

    $process = Start-Process `
        -FilePath $VenvPython `
        -ArgumentList $Arguments `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $OutLogPath `
        -RedirectStandardError $ErrLogPath `
        -WindowStyle Hidden `
        -PassThru

    Write-Host "$Name started. PID: $($process.Id)" -ForegroundColor Green
}

function Wait-HttpReady {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
            Write-Host "$Name is ready: $Url" -ForegroundColor Green
            return
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "$Name did not respond before timeout: $Url" -ForegroundColor Yellow
}

Assert-CommandReady
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

Write-Host "Starting NewsRec-RAG Agent..." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

if (-not $KeepExisting) {
    Stop-PortProcesses -Ports @($BackendPort, $FrontendPort)
    Start-Sleep -Seconds 1
}

if (Test-PortInUse -Port $BackendPort) {
    Write-Host "Backend port $BackendPort is already in use. Use -KeepExisting only when you really want to reuse it." -ForegroundColor Yellow
} else {
    $backendArgs = @("-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", "$BackendPort")
    if ($Reload) {
        $backendArgs = @("-m", "uvicorn", "app.main:app", "--reload", "--host", $HostAddress, "--port", "$BackendPort")
    }
    Start-ServiceProcess `
        -Name "FastAPI backend" `
        -Arguments $backendArgs `
        -OutLogPath $BackendOutLog `
        -ErrLogPath $BackendErrLog
}

Wait-HttpReady -Name "FastAPI backend" -Url "http://$HostAddress`:$BackendPort/health" -TimeoutSeconds 45

if (Test-PortInUse -Port $FrontendPort) {
    Write-Host "Frontend port $FrontendPort is already in use. Use -KeepExisting only when you really want to reuse it." -ForegroundColor Yellow
} else {
    Start-ServiceProcess `
        -Name "Streamlit frontend" `
        -Arguments @("-m", "streamlit", "run", "ui/streamlit_app.py", "--server.address", $HostAddress, "--server.port", "$FrontendPort", "--server.headless", "true") `
        -OutLogPath $FrontendOutLog `
        -ErrLogPath $FrontendErrLog
}

Wait-HttpReady -Name "Streamlit frontend" -Url "http://$HostAddress`:$FrontendPort" -TimeoutSeconds 30

Write-Host ""
Write-Host "Ready:" -ForegroundColor Cyan
Write-Host "  FastAPI API:  http://$HostAddress`:$BackendPort"
Write-Host "  API docs:     http://$HostAddress`:$BackendPort/docs"
Write-Host "  Streamlit UI: http://$HostAddress`:$FrontendPort"
Write-Host ""
Write-Host "Logs:" -ForegroundColor Cyan
Write-Host "  Backend out:  $BackendOutLog"
Write-Host "  Backend err:  $BackendErrLog"
Write-Host "  Frontend out: $FrontendOutLog"
Write-Host "  Frontend err: $FrontendErrLog"
Write-Host ""
Write-Host "To stop later, run:"
Write-Host "  Get-NetTCPConnection -LocalPort $BackendPort,$FrontendPort | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id `$_ }"
