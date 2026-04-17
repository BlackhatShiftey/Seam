param(
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

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$composeFile = Join-Path $repoRoot 'compose.yaml'
$exampleEnvFile = Join-Path $repoRoot '.env.example'

if (-not (Test-Path $EnvFile)) {
    Copy-Item $exampleEnvFile $EnvFile
    throw 'Created .env from .env.example. Edit POSTGRES_PASSWORD in .env, then rerun pgvector-up.ps1.'
}

$envMap = Get-SeamEnvMap $EnvFile
$password = if ($envMap.ContainsKey('POSTGRES_PASSWORD')) { $envMap['POSTGRES_PASSWORD'] } else { '' }
if (-not $password -or $password -eq 'CHANGE_ME') {
    throw 'Set POSTGRES_PASSWORD in .env before running pgvector-up.ps1.'
}

$dockerDesktop = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$dockerReady = $false
try {
    docker version *> $null
    $dockerReady = $LASTEXITCODE -eq 0
} catch {
    $dockerReady = $false
}

if (-not $dockerReady -and (Test-Path $dockerDesktop)) {
    Start-Process $dockerDesktop | Out-Null
    $deadline = (Get-Date).AddMinutes(2)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 5
        try {
            docker version *> $null
            if ($LASTEXITCODE -eq 0) {
                $dockerReady = $true
                break
            }
        } catch {
        }
    }
}

if (-not $dockerReady) {
    throw 'Docker is not ready. Start Docker Desktop and rerun this script.'
}

$existingContainer = docker ps -a --filter "name=^seam-pgvector$" --format '{{.ID}}'
if ($existingContainer) {
    docker rm -f seam-pgvector | Out-Null
}

$existingVolumes = docker volume ls --format '{{.Name}}' | Where-Object { $_ -match '(^|_)seam-pgvector-data$' }
foreach ($volume in $existingVolumes) {
    docker volume rm -f $volume | Out-Null
}

docker compose --file $composeFile up -d pgvector
if ($LASTEXITCODE -ne 0) {
    throw 'docker compose up failed'
}

$deadline = (Get-Date).AddMinutes(2)
while ((Get-Date) -lt $deadline) {
    $status = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' seam-pgvector 2>$null
    if ($status -eq 'healthy' -or $status -eq 'running') {
        break
    }
    Start-Sleep -Seconds 3
}

$dbHost = 'localhost'
$port = if ($envMap.ContainsKey('SEAM_PGVECTOR_PORT')) { $envMap['SEAM_PGVECTOR_PORT'] } else { '5432' }
$dbName = if ($envMap.ContainsKey('POSTGRES_DB')) { $envMap['POSTGRES_DB'] } else { 'seam' }
$userName = if ($envMap.ContainsKey('POSTGRES_USER')) { $envMap['POSTGRES_USER'] } else { 'seam' }

$env:PGPASSWORD = $password
$env:SEAM_PGVECTOR_TEST_DSN = "host=$dbHost port=$port dbname=$dbName user=$userName"
Write-Host 'SEAM pgvector is ready.'
Write-Host "SEAM_PGVECTOR_TEST_DSN=$($env:SEAM_PGVECTOR_TEST_DSN)"
Write-Host 'PGPASSWORD has been set for this PowerShell session.'
Write-Host 'Local pgvector volume was recreated to match the current .env credentials.'
Write-Host 'Run tests with: python -m unittest test_seam.py'
