param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8501,
    [string]$HostAddress = "127.0.0.1"
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

Assert-CommandReady
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

Write-Host "Starting NewsRec-RAG Agent..." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

if (Test-PortInUse -Port $BackendPort) {
    Write-Host "Backend port $BackendPort is already in use. Skipping backend startup." -ForegroundColor Yellow
} else {
    Start-ServiceProcess `
        -Name "FastAPI backend" `
        -Arguments @("-m", "uvicorn", "app.main:app", "--reload", "--host", $HostAddress, "--port", "$BackendPort") `
        -OutLogPath $BackendOutLog `
        -ErrLogPath $BackendErrLog
}

Start-Sleep -Seconds 2

if (Test-PortInUse -Port $FrontendPort) {
    Write-Host "Frontend port $FrontendPort is already in use. Skipping frontend startup." -ForegroundColor Yellow
} else {
    Start-ServiceProcess `
        -Name "Streamlit frontend" `
        -Arguments @("-m", "streamlit", "run", "ui/streamlit_app.py", "--server.address", $HostAddress, "--server.port", "$FrontendPort", "--server.headless", "true") `
        -OutLogPath $FrontendOutLog `
        -ErrLogPath $FrontendErrLog
}

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
