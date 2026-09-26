<#
.SYNOPSIS
    Runs the end-to-end (E2E) testcase pipeline flow for Document 8.pdf from the src/e2e directory.
#>

[CmdletBinding()]
param (
    [string]$PdfPath = "",
    [string]$OutputDir = "",
    [switch]$SkipPlanner,
    [switch]$NoBrowser
)

$CurrentDir = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if (-not $PdfPath) {
    $PdfPath = Join-Path $CurrentDir "Document 8.pdf"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $CurrentDir "output_document_8"
}

$RunScript = Join-Path $CurrentDir "run_e2e.ps1"
& "$RunScript" -PdfPath "$PdfPath" -OutputDir "$OutputDir" -SkipPlanner:$SkipPlanner -NoBrowser:$NoBrowser
