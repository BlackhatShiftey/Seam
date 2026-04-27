param(
    [ValidateRange(1024, 65535)]
    [int]$PgPort = 55432,

    [ValidateRange(1, 100)]
    [int]$WarnCpuPercent = 75,

    [ValidateRange(1, 100)]
    [int]$MaxCpuPercent = 85,

    [ValidateRange(1, 100)]
    [int]$WarnMemoryPercent = 82,

    [ValidateRange(1, 100)]
    [int]$MaxMemoryPercent = 90,

    [ValidateRange(1, 100)]
    [int]$WarnDiskPercent = 85,

    [ValidateRange(1, 100)]
    [int]$MaxDiskPercent = 92,

    [ValidatePattern("^[A-Za-z]:$")]
    [string]$Disk = "C:",

    [switch]$SkipPytest,
    [switch]$KeepContainer
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$guardScript = Join-Path $PSScriptRoot "run_guarded.ps1"
Set-Location $repoRoot

if (-not (Test-Path $guardScript)) {
    throw "Missing guarded runner: $guardScript"
}

function Invoke-GuardedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandText,

        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    $guardParams = @{
        Command = $CommandText
        WarnCpuPercent = $WarnCpuPercent
        MaxCpuPercent = $MaxCpuPercent
        WarnMemoryPercent = $WarnMemoryPercent
        MaxMemoryPercent = $MaxMemoryPercent
        WarnDiskPercent = $WarnDiskPercent
        MaxDiskPercent = $MaxDiskPercent
        Disk = $Disk
        SampleSeconds = 2
        BreachSamples = 3
        StopOnLimit = $true
    }

    & $guardScript @guardParams

    if ($LASTEXITCODE -ne 0) {
        throw "Guarded command failed (exit $LASTEXITCODE): $Label"
    }
}

function Invoke-Guarded {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    $quotedFile = "'" + ($FilePath -replace "'", "''") + "'"
    $quotedArgs = @()
    foreach ($arg in $ArgumentList) {
        $quotedArgs += "'" + ($arg -replace "'", "''") + "'"
    }
    $commandText = "& $quotedFile $($quotedArgs -join ' '); exit `$LASTEXITCODE"
    Invoke-GuardedCommand -CommandText $commandText -Label ("{0} {1}" -f $FilePath, ($ArgumentList -join " "))
}

function Remove-IfExists {
    param([string]$PathValue)
    if (Test-Path $PathValue) {
        Remove-Item -LiteralPath $PathValue -Recurse -Force
    }
}

docker version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not ready. Start Docker Desktop first."
}

$existing = Get-NetTCPConnection -State Listen -LocalPort $PgPort -ErrorAction SilentlyContinue
if ($existing) {
    throw "Port $PgPort is already in use. Pick a different -PgPort."
}

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$containerName = "seam-pgvector-guard-$stamp"
$volumeName = "$containerName-data"
$pgPassword = [guid]::NewGuid().ToString("N")
$dsn = "host=localhost port=$PgPort dbname=seam user=seam password=$pgPassword"

$sqliteDb = Join-Path $repoRoot ("real_adapter_sqlite_" + [guid]::NewGuid().ToString("N") + ".db")
$pgvectorDb = Join-Path $repoRoot ("real_adapter_pgvector_" + [guid]::NewGuid().ToString("N") + ".db")
$chromaPath = Join-Path $repoRoot (".seam_chroma_guard_" + [guid]::NewGuid().ToString("N"))
$oldDsn = $env:SEAM_PGVECTOR_DSN
$dsnWasSet = Test-Path Env:SEAM_PGVECTOR_DSN

try {
    Write-Host "[real-adapters] starting pgvector container..."
    docker run -d --rm `
        --name $containerName `
        -e POSTGRES_DB=seam `
        -e POSTGRES_USER=seam `
        -e POSTGRES_PASSWORD=$pgPassword `
        -e PGDATA=/var/lib/postgresql/data/pgdata `
        -p "${PgPort}:5432" `
        -v "${volumeName}:/var/lib/postgresql/data" `
        pgvector/pgvector:0.8.2-pg18-trixie *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to start pgvector container."
    }

    $ready = $false
    for ($i = 0; $i -lt 45; $i++) {
        $status = docker inspect -f "{{.State.Status}}" $containerName 2>$null
        if ($status -eq "running") {
            docker exec $containerName pg_isready -U seam -d seam *> $null
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
                break
            }
        }
        Start-Sleep -Seconds 2
    }

    if (-not $ready) {
        docker logs $containerName --tail 80
        throw "pgvector container was not ready in time."
    }

    docker exec $containerName psql -U seam -d seam -c "create extension if not exists vector;" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create pgvector extension."
    }

    Write-Host "[real-adapters] sqlite-vector + chroma smoke..."
    Invoke-Guarded -FilePath "python" -ArgumentList @("seam.py", "--db", $sqliteDb, "compile-nl", "SEAM real adapter smoke for sqlite and chroma retrieval.", "--persist")
    Invoke-Guarded -FilePath "python" -ArgumentList @("seam.py", "--db", $sqliteDb, "index", "--vector-backend", "seam", "--format", "json")
    Invoke-GuardedCommand -Label "sqlite retrieval gate" -CommandText @"
`$json = & python seam.py --db '$sqliteDb' retrieve 'seam_real_adapter_smoke_sqlite_chroma_retrieval' --vector-backend seam --trace --format json
`$obj = `$json | ConvertFrom-Json
if ((`$obj.candidates | Measure-Object).Count -lt 1) { throw 'Expected sqlite-vector retrieval candidate.' }
`$json
exit `$LASTEXITCODE
"@
    Invoke-Guarded -FilePath "python" -ArgumentList @("seam.py", "--db", $sqliteDb, "index", "--vector-backend", "chroma", "--vector-path", $chromaPath, "--vector-collection", "seam_hybrid_guard", "--format", "json")
    Invoke-GuardedCommand -Label "chroma retrieval gate" -CommandText @"
`$json = & python seam.py --db '$sqliteDb' retrieve 'seam_real_adapter_smoke_sqlite_chroma_retrieval' --vector-backend chroma --vector-path '$chromaPath' --vector-collection 'seam_hybrid_guard' --trace --format json
`$obj = `$json | ConvertFrom-Json
if ((`$obj.candidates | Measure-Object).Count -lt 1) { throw 'Expected chroma retrieval candidate.' }
`$json
exit `$LASTEXITCODE
"@

    Write-Host "[real-adapters] pgvector smoke..."
    $env:SEAM_PGVECTOR_DSN = $dsn
    Invoke-Guarded -FilePath "python" -ArgumentList @("seam.py", "doctor")
    Invoke-Guarded -FilePath "python" -ArgumentList @("seam.py", "--db", $pgvectorDb, "compile-nl", "SEAM real adapter smoke for pgvector retrieval.", "--persist")
    Invoke-GuardedCommand -Label "pgvector retrieval gate" -CommandText @"
`$json = & python seam.py --db '$pgvectorDb' retrieve 'seam_real_adapter_smoke_pgvector_retrieval' --trace --format json
`$obj = `$json | ConvertFrom-Json
if ((`$obj.candidates | Measure-Object).Count -lt 1) { throw 'Expected pgvector retrieval candidate.' }
`$json
exit `$LASTEXITCODE
"@

    if (-not $SkipPytest) {
        Write-Host "[real-adapters] full test suite under guard..."
        Invoke-Guarded -FilePath "python" -ArgumentList @("-m", "pytest", "-q")
    }

    Write-Host "[real-adapters] PASS"
} finally {
    if ($dsnWasSet) {
        $env:SEAM_PGVECTOR_DSN = $oldDsn
    } else {
        Remove-Item Env:SEAM_PGVECTOR_DSN -ErrorAction SilentlyContinue
    }

    Remove-IfExists -PathValue $sqliteDb
    Remove-IfExists -PathValue $pgvectorDb
    Remove-IfExists -PathValue $chromaPath

    if (-not $KeepContainer) {
        docker stop $containerName *> $null
    } else {
        Write-Host "[real-adapters] container left running: $containerName"
        Write-Host "[real-adapters] dsn: $dsn"
    }
}
