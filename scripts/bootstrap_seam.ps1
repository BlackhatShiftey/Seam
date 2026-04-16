param(
    [switch]$SkipPipUpgrade,
    [switch]$SkipGlobalShimInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$venvPython = Join-Path $repoRoot ".venv\\Scripts\\python.exe"
$venvActivate = Join-Path $repoRoot ".venv\\Scripts\\Activate.ps1"
$venvSeam = Join-Path $repoRoot ".venv\\Scripts\\seam.exe"
$venvBenchmark = Join-Path $repoRoot ".venv\\Scripts\\seam-benchmark.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment at .venv"
    python -m venv .venv
}

if (-not $SkipPipUpgrade) {
    & $venvPython -m pip install --upgrade pip
}

& $venvPython -m pip install -e .

if (-not (Test-Path $venvSeam)) {
    throw "Expected seam.exe to exist at $venvSeam after install."
}

if (-not (Test-Path $venvBenchmark)) {
    throw "Expected seam-benchmark.exe to exist at $venvBenchmark after install."
}

if (-not $SkipGlobalShimInstall) {
    & (Join-Path $PSScriptRoot "install_global_seam_command.ps1")
}

& $venvSeam doctor

Write-Host ""
Write-Host "SEAM bootstrap complete."
Write-Host "To use 'seam' directly in this shell, run:"
Write-Host "  . $venvActivate"
Write-Host ""
Write-Host "Then test:"
Write-Host "  seam --help"
Write-Host "  seam doctor"
Write-Host "  seam demo lossless tools/lossless_demo_input.txt demo.seamlx --min-savings 0.75"
