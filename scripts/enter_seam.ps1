$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$activateScript = Join-Path $repoRoot ".venv\\Scripts\\Activate.ps1"

if (-not (Test-Path $activateScript)) {
    throw "No .venv activation script found. Run .\\scripts\\bootstrap_seam.ps1 first."
}

. $activateScript

Write-Host "SEAM shell ready."
Write-Host "Try:"
Write-Host "  seam --help"
Write-Host "  seam doctor"
Write-Host "  seam --db seam.db dashboard"
Write-Host ""
Write-Host "If you installed the global shim, new shells can run 'seam' without activation too."
