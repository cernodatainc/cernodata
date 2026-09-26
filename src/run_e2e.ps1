<#
.SYNOPSIS
    Runs the end-to-end (E2E) testcase pipeline flow using PowerShell.

.DESCRIPTION
    1. Launches the interactive planner questionnaire for the target document.
    2. Waits for the user to complete the plan configuration.
    3. Runs pipeline parsing driven by the generated plan, storing outputs next to the testcase.
    4. Opens the generated interactive HTML viewer.

.PARAMETER PdfPath
    Path to the input PDF file (default: src/e2e/Dokument 5.pdf).

.PARAMETER OutputDir
    Output directory to store plan, DOM JSON, violations, and HTML viewer
    (default: src/e2e/output).
#>

[CmdletBinding()]
param (
    [string]$PdfPath = "",
    [string]$OutputDir = "",
    [switch]$SkipPlanner,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

# Determine repository root from script location (parent of src)
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
$RepoRoot = if (Test-Path (Join-Path $ScriptDir "..\src")) {
    [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
} elseif (Test-Path (Join-Path $ScriptDir "src")) {
    [System.IO.Path]::GetFullPath($ScriptDir)
} else {
    [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
}

$E2EDir = Join-Path $RepoRoot "src\e2e"
$DiscoveredPdfs = @(Get-ChildItem -Path $E2EDir -Filter "*.pdf" -File -ErrorAction SilentlyContinue | Sort-Object Name)

if (-not $PdfPath) {
    if ($DiscoveredPdfs.Count -gt 0) {
        $PdfPath = $DiscoveredPdfs[0].FullName
    } else {
        $PdfPath = Join-Path $E2EDir "Dokument 5.pdf"
    }
} elseif (-not (Test-Path $PdfPath)) {
    # Resolve relative to E2EDir if filename or relative path given
    $Candidate = Join-Path $E2EDir $PdfPath
    if (Test-Path $Candidate) {
        $PdfPath = $Candidate
    }
}

if (-not $OutputDir) {
    $DocBaseName = [System.IO.Path]::GetFileNameWithoutExtension($PdfPath)
    $NormalizedName = $DocBaseName.ToLower() -replace '\s+', '_'
    $Candidates = @(
        (Join-Path $E2EDir "output_$NormalizedName"),
        (Join-Path $E2EDir "output_$DocBaseName"),
        (Join-Path $E2EDir "output\$DocBaseName")
    )
    $FoundCandidate = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($FoundCandidate) {
        $OutputDir = $FoundCandidate
    } else {
        $OutputDir = Join-Path $E2EDir "output"
    }
}

# Resolve full paths based on current location before changing directory
if (-not [System.IO.Path]::IsPathRooted($PdfPath)) {
    $PdfPath = Join-Path (Get-Location).Path $PdfPath
}
if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = Join-Path (Get-Location).Path $OutputDir
}

$PdfPath = [System.IO.Path]::GetFullPath($PdfPath)
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)

if (-not (Test-Path $PdfPath)) {
    Write-Error "Input document not found: $PdfPath"
    exit 1
}

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "===================================================================="
Write-Host "cernodata E2E Pipeline Flow: $PdfPath"
Write-Host "===================================================================="
Write-Host "Input Document:   $PdfPath"
Write-Host "Output Directory: $OutputDir"
Write-Host "Repository Root:  $RepoRoot"
Write-Host ""

# Ensure PYTHONPATH includes repo root and execute from repo root
$OldPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$RepoRoot;$env:PYTHONPATH" } else { $RepoRoot }

Push-Location $RepoRoot
try {
    $PlanPath = Join-Path $OutputDir "plan.json"

    if ($SkipPlanner -and (Test-Path $PlanPath)) {
        Write-Host "[Step 1/3] Using existing execution plan: $PlanPath (-SkipPlanner)"
    } else {
        # Step 1: Launch interactive planner wizard
        Write-Host "[Step 1/3] Launching interactive planner wizard..."
        Write-Host "Please answer the questionnaire prompts to generate the plan."
        Write-Host ""

        & python -m src.main --create-plan --plan-only --input "$PdfPath" --output-dir "$OutputDir"

        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PlanPath)) {
            Write-Error "Planner questionnaire failed or plan was not generated: $PlanPath"
            exit 1
        }
    }

    # Step 2: Run pipeline parsing using generated plan
    Write-Host ""
    Write-Host "[Step 2/3] Executing pipeline with generated plan: $PlanPath..."
    & python -m src.main --plan "$PlanPath" --input "$PdfPath" --output-dir "$OutputDir"

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Pipeline parsing failed."
        exit 1
    }

    # Step 3: Launch interactive HTML viewer
    $HtmlViewerPath = Join-Path $OutputDir "interactive_viewer.html"
    if (Test-Path $HtmlViewerPath) {
        Write-Host ""
        Write-Host "[Step 3/3] Interactive HTML viewer generated: $HtmlViewerPath"
        if (-not $NoBrowser) {
            Start-Process "$HtmlViewerPath"
        }
    } else {
        Write-Warning "Interactive HTML viewer not found: $HtmlViewerPath"
    }

    Write-Host ""
    Write-Host "===================================================================="
    Write-Host "[OK] E2E Pipeline flow completed successfully."
    Write-Host "===================================================================="
}
finally {
    Pop-Location
    $env:PYTHONPATH = $OldPythonPath
}
