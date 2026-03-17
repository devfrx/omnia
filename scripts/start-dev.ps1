# ------------------------------------------------
# O.M.N.I.A. - Start Development Environment
# ------------------------------------------------
# Run: .\scripts\start-dev.ps1

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipOllama,
    [switch]$Trellis
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  O.M.N.I.A. - Dev Mode" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# -- 1. Ensure Ollama is running --
if (-not $SkipOllama -and -not $FrontendOnly) {
    $ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $ollamaProc) {
        Write-Host "  -> Starting Ollama..." -ForegroundColor Yellow
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "  [OK] Ollama running on :11434" -ForegroundColor Green
    } else {
        Write-Host "  [OK] Ollama already running" -ForegroundColor Green
    }
}

# -- 2. Start Backend --
if (-not $FrontendOnly) {
    Write-Host "  -> Starting FastAPI backend..." -ForegroundColor Yellow

    $backendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location $root
        & "backend\.venv\Scripts\python.exe" -m uvicorn backend.core.app:create_app --factory --reload --reload-dir backend --host 0.0.0.0 --port 8000
    } -ArgumentList $Root

    Write-Host "  [OK] Backend starting on :8000 (Job: $($backendJob.Id))" -ForegroundColor Green
}

# -- 3. Start Frontend --
if (-not $BackendOnly) {
    Write-Host "  -> Starting Electron + Vue dev..." -ForegroundColor Yellow

    $frontendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm run dev
    } -ArgumentList $Root

    Write-Host "  [OK] Frontend starting (Job: $($frontendJob.Id))" -ForegroundColor Green
}

# -- 4. Start TRELLIS (optional) --
$trellisJob = $null
if ($Trellis -and -not $FrontendOnly) {
    $TrellisDir = Join-Path (Split-Path -Parent $Root) "TRELLIS-for-windows"
    $TrellisPython = Join-Path $TrellisDir ".venv\Scripts\python.exe"
    $TrellisServer = Join-Path $Root "trellis_server\server.py"
    $TrellisOutput = Join-Path $Root "data\3d_models"

    if ((Test-Path $TrellisPython) -and (Test-Path $TrellisServer)) {
        Write-Host "  -> Starting TRELLIS 3D microservice..." -ForegroundColor Yellow
        if (-not (Test-Path $TrellisOutput)) {
            New-Item -ItemType Directory -Path $TrellisOutput -Force | Out-Null
        }
        $trellisJob = Start-Job -ScriptBlock {
            param($trellisDir, $python, $server, $outputDir)
            Set-Location $trellisDir
            & $python $server --model TRELLIS-text-large --port 8090 --output-dir $outputDir
        } -ArgumentList $TrellisDir, $TrellisPython, $TrellisServer, $TrellisOutput
        Write-Host "  [OK] TRELLIS starting on :8090 (Job: $($trellisJob.Id))" -ForegroundColor Green
    } else {
        Write-Host "  [!] TRELLIS not installed - run: .\scripts\start-trellis.ps1 -Install" -ForegroundColor Yellow
    }
}

# -- Status --
Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Ollama:         http://localhost:11434" -ForegroundColor Cyan
if ($trellisJob) {
    Write-Host "  TRELLIS 3D:     http://localhost:8090" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# -- Wait and cleanup --
try {
    while ($true) {
        if (-not $FrontendOnly -and $backendJob) {
            $out = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue
            if ($out) { Write-Host "[BACKEND] $out" }
        }
        if (-not $BackendOnly -and $frontendJob) {
            $out = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue
            if ($out) { Write-Host "[FRONTEND] $out" }
        }
        if ($trellisJob) {
            $out = Receive-Job -Job $trellisJob -ErrorAction SilentlyContinue
            if ($out) { Write-Host "[TRELLIS] $out" }
        }
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "  Stopping services..." -ForegroundColor Yellow
    Get-Job | Stop-Job -PassThru | Remove-Job
    Write-Host "  [OK] All services stopped." -ForegroundColor Green
}