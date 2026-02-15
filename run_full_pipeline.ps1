param(
    [switch]$SkipInstall,
    [switch]$SkipInit,
    [ValidateSet("demo", "bulk", "none")]
    [string]$SeedMode = "demo",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    throw "Missing .venv python at $pythonExe. Create it with: python -m venv .venv"
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=================================================="
    Write-Host $Message
    Write-Host "=================================================="
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$PyArgs)

    Write-Host ">> $pythonExe $($PyArgs -join ' ')"
    & $pythonExe @PyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $($PyArgs -join ' ')"
    }
}

function Wait-ForReview {
    param([Parameter(Mandatory = $true)][string]$StageName)

    if ($NonInteractive) {
        return
    }

    Write-Host ""
    Write-Host "Review gate: $StageName"
    Write-Host "Open dashboard in another terminal and complete approvals/rejections:"
    Write-Host "  .\.venv\Scripts\python.exe -m streamlit run app/multi_agent_dashboard.py"
    Read-Host "Press Enter when review for '$StageName' is complete"
}

Write-Step "RIVO Full Pipeline Runner"

if (-not $SkipInstall) {
    Write-Step "Installing/Updating Dependencies"
    Invoke-Python -PyArgs @("-m", "pip", "install", "-r", "requirements.txt")
}

if (-not $SkipInit) {
    Write-Step "Initializing Database"
    Invoke-Python -PyArgs @("-m", "app.database.init_db")
}

Write-Step "Seeding Data"
switch ($SeedMode) {
    "demo" { Invoke-Python -PyArgs @("scripts/seed_data.py") }
    "bulk" { Invoke-Python -PyArgs @("scripts/seed_20_leads.py") }
    "none" { Write-Host "Skipping seeding (SeedMode=none)." }
}

Write-Step "Stage 1: SDR"
Invoke-Python -PyArgs @("app/orchestrator.py", "sdr")
Wait-ForReview -StageName "SDR"

Write-Step "Stage 2: Sales"
Invoke-Python -PyArgs @("app/orchestrator.py", "sales")
Wait-ForReview -StageName "Sales"

Write-Step "Stage 3: Negotiation"
Invoke-Python -PyArgs @("app/orchestrator.py", "negotiation")
Wait-ForReview -StageName "Negotiation"

Write-Step "Stage 4: Finance"
Invoke-Python -PyArgs @("app/orchestrator.py", "finance")
Wait-ForReview -StageName "Finance"

Write-Step "Final Health + Data Snapshot"
Invoke-Python -PyArgs @("app/orchestrator.py", "health")
Invoke-Python -PyArgs @("scripts/view_all_data.py")

Write-Host ""
Write-Host "Pipeline run complete."
