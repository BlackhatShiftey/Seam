param(
    [string]$UserName,
    [string]$DatabaseName,
    [string]$Port = '5432',
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\.env')
)

function Get-SeamEnvMap {
    param([string]$Path)
    $values = @{}
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        $pair = $trimmed -split '=', 2
        if ($pair.Length -ne 2) {
            continue
        }
        $values[$pair[0].Trim()] = $pair[1].Trim()
    }
    return $values
}

function Set-SeamEnvMap {
    param([string]$Path, [hashtable]$Values)
    @(
        "POSTGRES_DB=$($Values['POSTGRES_DB'])",
        "POSTGRES_USER=$($Values['POSTGRES_USER'])",
        "POSTGRES_PASSWORD=$($Values['POSTGRES_PASSWORD'])",
        "SEAM_PGVECTOR_PORT=$($Values['SEAM_PGVECTOR_PORT'])"
    ) | Set-Content -Encoding utf8 $Path
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$requirementsFile = Join-Path $repoRoot 'requirements.txt'
$exampleEnvFile = Join-Path $repoRoot '.env.example'
$pgvectorScript = Join-Path $PSScriptRoot 'pgvector-up.ps1'

if (-not (Test-Path $EnvFile)) {
    Copy-Item $exampleEnvFile $EnvFile
    Write-Host "Created $EnvFile from .env.example"
    Write-Host 'Edit .env and set POSTGRES_PASSWORD before rerunning setup.'
    exit 1
}

$envMap = Get-SeamEnvMap $EnvFile
if ($UserName) { $envMap['POSTGRES_USER'] = $UserName }
if ($DatabaseName) { $envMap['POSTGRES_DB'] = $DatabaseName }
if ($Port) { $envMap['SEAM_PGVECTOR_PORT'] = $Port }
if (-not $envMap.ContainsKey('POSTGRES_USER') -or -not $envMap['POSTGRES_USER']) { $envMap['POSTGRES_USER'] = 'seam' }
if (-not $envMap.ContainsKey('POSTGRES_DB') -or -not $envMap['POSTGRES_DB']) { $envMap['POSTGRES_DB'] = 'seam' }
if (-not $envMap.ContainsKey('SEAM_PGVECTOR_PORT') -or -not $envMap['SEAM_PGVECTOR_PORT']) { $envMap['SEAM_PGVECTOR_PORT'] = '5432' }
if (-not $envMap.ContainsKey('POSTGRES_PASSWORD') -or -not $envMap['POSTGRES_PASSWORD'] -or $envMap['POSTGRES_PASSWORD'] -eq 'CHANGE_ME') {
    Set-SeamEnvMap -Path $EnvFile -Values $envMap
    throw 'Set POSTGRES_PASSWORD in .env before running setup-seam.ps1.'
}

Set-SeamEnvMap -Path $EnvFile -Values $envMap
Write-Host "Using config from $EnvFile"
python -m pip install -r $requirementsFile
if ($LASTEXITCODE -ne 0) {
    throw 'pip install failed'
}

& $pgvectorScript -EnvFile $EnvFile
if ($LASTEXITCODE -ne 0) {
    throw 'pgvector bootstrap failed'
}

Write-Host 'SEAM setup complete.'
Write-Host 'Next step: python -m unittest test_seam.py'
