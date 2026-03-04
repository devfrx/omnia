# ──────────────────────────────────────────────────
# O.M.N.I.A. — Setup Script (Windows)
# ──────────────────────────────────────────────────
# Run: .\scripts\setup.ps1

param(
    [switch]$SkipOllama,
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  O.M.N.I.A. — Setup" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check prerequisites ──────────────────────
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

# Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "  ✗ Python not found. Install Python 3.11+ from python.org" -ForegroundColor Red
    exit 1
}
$pyVersion = python --version 2>&1
Write-Host "  ✓ $pyVersion" -ForegroundColor Green

# Node
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "  ✗ Node.js not found. Install from nodejs.org" -ForegroundColor Red
    exit 1
}
$nodeVersion = node --version 2>&1
Write-Host "  ✓ Node.js $nodeVersion" -ForegroundColor Green

# uv
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "  → Installing uv..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
}
Write-Host "  ✓ uv $(uv --version 2>&1)" -ForegroundColor Green

# ── 2. Backend setup ────────────────────────────
Write-Host ""
Write-Host "[2/6] Setting up Python backend..." -ForegroundColor Yellow

Push-Location "$Root\backend"
if (-not (Test-Path ".venv")) {
    uv venv .venv
}
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
Pop-Location
Write-Host "  ✓ Backend dependencies installed" -ForegroundColor Green

# ── 3. Frontend setup ───────────────────────────
Write-Host ""
Write-Host "[3/6] Setting up Electron frontend..." -ForegroundColor Yellow

Push-Location "$Root\frontend"
npm install
Pop-Location
Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green

# ── 4. Ollama ───────────────────────────────────
if (-not $SkipOllama) {
    Write-Host ""
    Write-Host "[4/6] Checking Ollama..." -ForegroundColor Yellow

    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) {
        Write-Host "  → Installing Ollama via winget..." -ForegroundColor Yellow
        winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements
    }
    Write-Host "  ✓ Ollama installed" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[4/6] Skipping Ollama (--SkipOllama)" -ForegroundColor DarkGray
}

# ── 5. Download models ──────────────────────────
if (-not $SkipModels -and -not $SkipOllama) {
    Write-Host ""
    Write-Host "[5/6] Pulling LLM model (this may take a while)..." -ForegroundColor Yellow
    
    # Start Ollama if not running
    $ollamaProc = Get-Process ollama -ErrorAction SilentlyContinue
    if (-not $ollamaProc) {
        Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    
    ollama pull qwen2.5:14b
    Write-Host "  ✓ Qwen 2.5 14B downloaded" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[5/6] Skipping model download" -ForegroundColor DarkGray
}

# ── 6. Create data directory ────────────────────
Write-Host ""
Write-Host "[6/6] Creating data directories..." -ForegroundColor Yellow

$dataDirs = @("$Root\data", "$Root\models\stt", "$Root\models\tts", "$Root\models\llm")
foreach ($d in $dataDirs) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}
Write-Host "  ✓ Data directories ready" -ForegroundColor Green

# ── Done ────────────────────────────────────────
Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host "  O.M.N.I.A. setup complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Next: .\scripts\start-dev.ps1" -ForegroundColor Cyan
Write-Host ""
