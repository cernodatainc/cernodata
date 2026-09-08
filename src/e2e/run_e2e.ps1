<#
.SYNOPSIS
    Runs the end-to-end (E2E) testcase pipeline flow from the src/e2e directory.

.PARAMETER PdfPath
    Path to the input PDF file (default: src/e2e/Dokument 5.pdf).

.PARAMETER OutputDir
    Output directory to store plan, DOM JSON, violations, and HTML viewer
    (default: src/e2e/output).
#>

[CmdletBinding()]
param (
    [string]$PdfPath = "",
    [string]$OutputDir = ""
)

$CurrentDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if (-not $PdfPath) {
    $PdfPath = Join-Path $CurrentDir "Dokument 5.pdf"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $CurrentDir "output"
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $CurrentDir "../.."))
$RunScript = Join-Path $RepoRoot "run_e2e.ps1"

& "$RunScript" -PdfPath "$PdfPath" -OutputDir "$OutputDir"
