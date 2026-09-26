<#
.SYNOPSIS
    Runs the end-to-end (E2E) testcase pipeline flow from the src/e2e directory.

.PARAMETER PdfPath
    Path or filename of the target PDF (default: autodiscovered from src/e2e).

.PARAMETER OutputDir
    Output directory to store plan, DOM JSON, violations, and HTML viewer.
#>

[CmdletBinding()]
param (
    [string]$PdfPath = "",
    [string]$OutputDir = "",
    [switch]$SkipPlanner,
    [switch]$NoBrowser
)

$CurrentDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $CurrentDir "../.."))
$RunScript = Join-Path $RepoRoot "src\run_e2e.ps1"

& "$RunScript" -PdfPath "$PdfPath" -OutputDir "$OutputDir" -SkipPlanner:$SkipPlanner -NoBrowser:$NoBrowser
