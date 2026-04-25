param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$DashboardArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

if (-not $env:SEAM_DB_PATH) {
    $installedDb = Join-Path $env:LOCALAPPDATA "SEAM\state\seam.db"
    if (Test-Path $installedDb) {
        $env:SEAM_DB_PATH = $installedDb
    }
}

function Read-DotEnv {
    param([Parameter(Mandatory = $true)][string]$Path)

    $values = @{}
    foreach ($line in Get-Content -Path $Path) {
        if ($line -match "^\s*#" -or $line -notmatch "=") {
            continue
        }
        $key, $value = $line -split "=", 2
        $key = $key.Trim()
        $value = $value.Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($key) {
            $values[$key] = $value
        }
    }
    return $values
}

function ConvertTo-ConnInfoValue {
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) {
        return "''"
    }
    $escaped = $Value.Replace("\", "\\").Replace("'", "\'")
    return "'$escaped'"
}

if (-not $env:SEAM_PGVECTOR_DSN -and (Test-Path ".env")) {
    $envValues = Read-DotEnv -Path ".env"
    $required = @("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "SEAM_PGVECTOR_PORT")
    $hasPgConfig = $true
    foreach ($key in $required) {
        if (-not $envValues.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envValues[$key])) {
            $hasPgConfig = $false
        }
    }

    if ($hasPgConfig) {
        $parts = @(
            "host=$(ConvertTo-ConnInfoValue 'localhost')",
            "port=$(ConvertTo-ConnInfoValue $envValues['SEAM_PGVECTOR_PORT'])",
            "dbname=$(ConvertTo-ConnInfoValue $envValues['POSTGRES_DB'])",
            "user=$(ConvertTo-ConnInfoValue $envValues['POSTGRES_USER'])",
            "password=$(ConvertTo-ConnInfoValue $envValues['POSTGRES_PASSWORD'])"
        )
        $env:SEAM_PGVECTOR_DSN = $parts -join " "
    }
}

$useSystemPython = [bool]$env:SEAM_PGVECTOR_DSN
$exitCode = 0

if ($useSystemPython -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python seam.py dashboard @DashboardArgs
    $exitCode = $LASTEXITCODE
} elseif (Test-Path ".venv\Scripts\seam-dash.exe") {
    & ".venv\Scripts\seam-dash.exe" @DashboardArgs
    $exitCode = $LASTEXITCODE
} elseif (Test-Path ".venv\Scripts\python.exe") {
    & ".venv\Scripts\python.exe" -m seam_runtime.dashboard @DashboardArgs
    $exitCode = $LASTEXITCODE
} else {
    Write-Host "Missing repo-local virtual environment."
    Write-Host "Create it from the repo root with:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -e `".[dash]`""
    $exitCode = 1
}

exit $exitCode
