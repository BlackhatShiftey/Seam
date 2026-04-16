$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$pathEntries = @()
if ($userPath) {
    $pathEntries = $userPath -split ";" | Where-Object { $_ }
}

$preferredTarget = $null
$pythonUserScripts = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\Scripts"
if ($pathEntries -contains $pythonUserScripts -and (Test-Path $pythonUserScripts)) {
    $preferredTarget = $pythonUserScripts
}

if (-not $preferredTarget) {
    $preferredTarget = Join-Path $env:LOCALAPPDATA "SEAM\\bin"
    if (-not (Test-Path $preferredTarget)) {
        New-Item -ItemType Directory -Path $preferredTarget -Force | Out-Null
    }
    if ($pathEntries -notcontains $preferredTarget) {
        $newUserPath = ($pathEntries + $preferredTarget) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $newUserPath, "User")
        if ($env:PATH -notlike "*$preferredTarget*") {
            $env:PATH = $env:PATH.TrimEnd(";") + ";" + $preferredTarget
        }
    }
}

$seamExe = Join-Path $repoRoot ".venv\\Scripts\\seam.exe"
$benchmarkExe = Join-Path $repoRoot ".venv\\Scripts\\seam-benchmark.exe"
$bootstrapScript = Join-Path $repoRoot "scripts\\bootstrap_seam.ps1"

$seamShim = @"
@echo off
set "SEAM_EXE=$seamExe"
if not exist "%SEAM_EXE%" (
  echo SEAM is not bootstrapped in $repoRoot
  echo Run: powershell -ExecutionPolicy Bypass -File "$bootstrapScript"
  exit /b 1
)
"%SEAM_EXE%" %*
exit /b %ERRORLEVEL%
"@

$benchmarkShim = @"
@echo off
set "SEAM_BENCHMARK_EXE=$benchmarkExe"
if not exist "%SEAM_BENCHMARK_EXE%" (
  echo SEAM benchmark is not bootstrapped in $repoRoot
  echo Run: powershell -ExecutionPolicy Bypass -File "$bootstrapScript"
  exit /b 1
)
"%SEAM_BENCHMARK_EXE%" %*
exit /b %ERRORLEVEL%
"@

Set-Content -Path (Join-Path $preferredTarget "seam.cmd") -Value $seamShim -Encoding ASCII
Set-Content -Path (Join-Path $preferredTarget "seam-benchmark.cmd") -Value $benchmarkShim -Encoding ASCII

Write-Host "Installed SEAM shims to $preferredTarget"
Write-Host "You can now open a new shell and run:"
Write-Host "  seam doctor"
Write-Host "  seam --help"
