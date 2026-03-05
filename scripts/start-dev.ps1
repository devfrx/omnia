# ──────────────────────────────────────────────────
# O.M.N.I.A. — Start Development Environment
# ──────────────────────────────────────────────────
# Run: .\scripts\start-dev.ps1

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$SkipOllama
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  O.M.N.I.A. — Dev Mode" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. Ensure Ollama is running ─────────────────
if (-not $SkipOllama -and -not $FrontendOnly) {
    $ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $ollamaProc) {
        Write-Host "  → Starting Ollama..." -ForegroundColor Yellow
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 2
        Write-Host "  ✓ Ollama running on :11434" -ForegroundColor Green
    } else {
        Write-Host "  ✓ Ollama already running" -ForegroundColor Green
    }
}

# ── 2. Start Backend ───────────────────────────
if (-not $FrontendOnly) {
    Write-Host "  → Starting FastAPI backend..." -ForegroundColor Yellow
    
    $backendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location $root
        & "backend\.venv\Scripts\python.exe" -m uvicorn backend.core.app:create_app --factory --reload --reload-dir backend --host 0.0.0.0 --port 8000
    } -ArgumentList $Root
    
    Write-Host "  ✓ Backend starting on :8000 (Job: $($backendJob.Id))" -ForegroundColor Green
}

# ── 3. Start Frontend ──────────────────────────
if (-not $BackendOnly) {
    Write-Host "  → Starting Electron + Vue dev..." -ForegroundColor Yellow
    
    $frontendJob = Start-Job -ScriptBlock {
        param($root)
        Set-Location "$root\frontend"
        npm run dev
    } -ArgumentList $Root
    
    Write-Host "  ✓ Frontend starting (Job: $($frontendJob.Id))" -ForegroundColor Green
}

# ── Status ──────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:    http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs:       http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  Ollama:         http://localhost:11434" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host ""

# ── Wait and cleanup ───────────────────────────
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
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "  Stopping services..." -ForegroundColor Yellow
    Get-Job | Stop-Job -PassThru | Remove-Job
    Write-Host "  ✓ All services stopped." -ForegroundColor Green
}
