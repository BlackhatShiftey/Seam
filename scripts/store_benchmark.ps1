param(
    [ValidateSet("all", "lossless", "retrieval", "embedding", "long_context", "persistence", "agent_tasks")]
    [string]$Suite = "all",

    [ValidateSet("auto", "char4_approx", "cl100k_base", "o200k_base")]
    [string]$Tokenizer = "auto",

    [double]$MinSavings = 0.30,

    [string]$DbPath = "seam.db",

    [string]$OutputRoot = "",

    [switch]$IncludeMachineText,
    [switch]$NoGuard,
    [switch]$AllowRepoOutput
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $documents = [Environment]::GetFolderPath("MyDocuments")
    $OutputRoot = Join-Path $documents "SEAM\benchmarks"
}

$repoRootFull = [System.IO.Path]::GetFullPath($repoRoot)
$outputRootFull = [System.IO.Path]::GetFullPath($OutputRoot)
if (-not $AllowRepoOutput -and $outputRootFull.StartsWith($repoRootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot points into the git repo. Use a local path outside repo (default: Documents\\SEAM\\benchmarks)."
}

$dateFolder = Get-Date -Format "yyyy-MM-dd"
$suiteFolder = Join-Path (Join-Path $outputRootFull $Suite) $dateFolder
New-Item -ItemType Directory -Force -Path $suiteFolder | Out-Null

$tmpJson = Join-Path $env:TEMP ("seam_benchmark_" + [guid]::NewGuid().ToString("N") + ".json")
$minSavingsText = $MinSavings.ToString("0.00", [System.Globalization.CultureInfo]::InvariantCulture)

$args = @(
    "seam.py",
    "--db", $DbPath,
    "benchmark", "run", $Suite,
    "--persist",
    "--output", $tmpJson,
    "--format", "json",
    "--tokenizer", $Tokenizer,
    "--min-savings", $minSavingsText
)
if ($IncludeMachineText) {
    $args += "--include-machine-text"
}

$commandForRecord = "python " + ($args -join " ")

try {
    if ($NoGuard) {
        & python @args
        if ($LASTEXITCODE -ne 0) {
            throw "Benchmark command failed (exit $LASTEXITCODE)."
        }
    } else {
        $guardScript = Join-Path $PSScriptRoot "run_guarded.ps1"
        if (-not (Test-Path $guardScript)) {
            throw "Guard script missing: $guardScript"
        }
        $quotedArgs = @()
        foreach ($arg in $args) {
            $quotedArgs += "'" + ($arg -replace "'", "''") + "'"
        }
        $commandText = "& 'python' $($quotedArgs -join ' '); exit `$LASTEXITCODE"
        & $guardScript `
            -Command $commandText `
            -WarnCpuPercent 75 `
            -MaxCpuPercent 85 `
            -WarnMemoryPercent 82 `
            -MaxMemoryPercent 90 `
            -WarnDiskPercent 85 `
            -MaxDiskPercent 92 `
            -Disk "C:" `
            -SampleSeconds 2 `
            -BreachSamples 3 `
            -StopOnLimit
        if ($LASTEXITCODE -ne 0) {
            throw "Guarded benchmark command failed (exit $LASTEXITCODE)."
        }
    }

    if (-not (Test-Path $tmpJson)) {
        throw "Benchmark output file was not produced: $tmpJson"
    }

    $reportText = Get-Content -Raw -LiteralPath $tmpJson
    $report = $reportText | ConvertFrom-Json

    if (-not $report.bundle_hash) { throw "Missing bundle_hash in benchmark report." }
    if (-not $report.manifest) { throw "Missing manifest in benchmark report." }
    if (-not $report.manifest.git_sha) { throw "Missing manifest.git_sha in benchmark report." }
    if (-not $report.manifest.dataset_hashes) { throw "Missing manifest.dataset_hashes in benchmark report." }
    if (-not $report.manifest.dependencies) { throw "Missing manifest.dependencies in benchmark report." }

    $caseHashes = @()
    foreach ($familyProp in $report.families.PSObject.Properties) {
        $family = $familyProp.Value
        if ($family.cases) {
            foreach ($case in $family.cases) {
                if (-not $case.case_hash) {
                    throw "Missing case_hash for case $($case.case_id)."
                }
                $caseHashes += [ordered]@{
                    family = $family.family
                    case_id = $case.case_id
                    case_hash = $case.case_hash
                    status = $case.status
                }
            }
        }
    }
    if ($caseHashes.Count -lt 1) {
        throw "No case hashes were found in benchmark report."
    }

    $runIdRaw = [string]$report.manifest.run_id
    $runIdSafe = $runIdRaw -replace "[:\\/*?\""<>\|]", "-"
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"

    $maxSequence = 0
    $existingRunDirs = Get-ChildItem -LiteralPath $suiteFolder -Directory -ErrorAction SilentlyContinue
    foreach ($dir in $existingRunDirs) {
        if ($dir.Name -match '^(\d{3})_') {
            $value = [int]$matches[1]
            if ($value -gt $maxSequence) {
                $maxSequence = $value
            }
        }
    }
    $sequenceText = "{0:D3}" -f ($maxSequence + 1)
    $runFolder = Join-Path $suiteFolder ($sequenceText + "_" + $timestamp + "_" + $runIdSafe)
    New-Item -ItemType Directory -Force -Path $runFolder | Out-Null

    $reportPath = Join-Path $runFolder "benchmark_report.json"
    $commandPath = Join-Path $runFolder "command.txt"
    $publicationPath = Join-Path $runFolder "publication_manifest.json"
    $caseHashPath = Join-Path $runFolder "case_hashes.json"
    $researchNotesPath = Join-Path $runFolder "research_notes.md"
    $envSnapshotPath = Join-Path $runFolder "environment_snapshot.json"

    Set-Content -LiteralPath $reportPath -Value $reportText -Encoding utf8
    Set-Content -LiteralPath $commandPath -Value $commandForRecord -Encoding utf8
    ($caseHashes | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath $caseHashPath -Encoding utf8

    $publication = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        daily_run_sequence = $sequenceText
        command = $commandForRecord
        suite = $Suite
        run_id = $report.manifest.run_id
        bundle_hash = $report.bundle_hash
        git_sha = $report.manifest.git_sha
        tokenizer = $report.manifest.tokenizer
        dependencies = $report.manifest.dependencies
        fixture_hashes = $report.manifest.dataset_hashes
        case_hashes = $caseHashes
        summary = $report.summary
    }
    ($publication | ConvertTo-Json -Depth 100) | Set-Content -LiteralPath $publicationPath -Encoding utf8

    $gitStatus = (& git status --short 2>$null) -join "`n"
    $envSnapshot = [ordered]@{
        generated_at = (Get-Date).ToString("o")
        sequence = $sequenceText
        daily_run_sequence = $sequenceText
        output_root = $outputRootFull
        run_folder = $runFolder
        machine_name = $env:COMPUTERNAME
        user_name = $env:USERNAME
        powershell_version = $PSVersionTable.PSVersion.ToString()
        python = $report.manifest.python
        platform = $report.manifest.platform
        db_path = $DbPath
        git_sha = $report.manifest.git_sha
        git_status = $gitStatus
    }
    ($envSnapshot | ConvertTo-Json -Depth 20) | Set-Content -LiteralPath $envSnapshotPath -Encoding utf8

    $summaryStatus = [string]$report.summary.status
    $summaryPass = [string]$report.summary.passed_cases
    $summaryTotal = [string]$report.summary.case_count
    $notes = @"
# Benchmark Research Notes

- generated_at: $($publication.generated_at)
- sequence: $sequenceText
- daily_run_sequence: $sequenceText
- suite: $Suite
- run_id: $($report.manifest.run_id)
- status: $summaryStatus
- passed_cases: $summaryPass/$summaryTotal
- bundle_hash: $($report.bundle_hash)
- git_sha: $($report.manifest.git_sha)
- tokenizer: $($report.manifest.tokenizer)

## Documentation Rule Checklist

- command used: recorded in `command.txt`
- bundle hash: recorded in `publication_manifest.json`
- per-case hashes: recorded in `case_hashes.json`
- fixture hashes: recorded in `publication_manifest.json`
- tokenizer/dependency state: recorded in `publication_manifest.json`
- git SHA: recorded in `publication_manifest.json`

## Research Discipline

- Claims in external docs should reference this run folder and its hashes.
- Do not claim improvements without comparing prior run artifacts.
- Keep interpretation separate from raw report data.
"@
    Set-Content -LiteralPath $researchNotesPath -Value $notes -Encoding utf8

    $indexPath = Join-Path $suiteFolder "_index.json"
    $indexRows = @()
    if (Test-Path $indexPath) {
        try {
            $existingIndex = Get-Content -Raw -LiteralPath $indexPath | ConvertFrom-Json
            if ($existingIndex) {
                $indexRows = @($existingIndex)
            }
        } catch {
            $indexRows = @()
        }
    }
    $indexRows += [ordered]@{
        sequence = $sequenceText
        daily_run_sequence = $sequenceText
        timestamp = $timestamp
        run_id = $report.manifest.run_id
        suite = $Suite
        status = $summaryStatus
        case_count = $summaryTotal
        passed_cases = $summaryPass
        bundle_hash = $report.bundle_hash
        folder = $runFolder
    }
    ($indexRows | ConvertTo-Json -Depth 20) | Set-Content -LiteralPath $indexPath -Encoding utf8

    Write-Host "[benchmark-store] stored run at: $runFolder"
    Write-Host "[benchmark-store] bundle_hash: $($report.bundle_hash)"
    Write-Host "[benchmark-store] status: $summaryStatus ($summaryPass/$summaryTotal)"
} finally {
    if (Test-Path $tmpJson) {
        Remove-Item -LiteralPath $tmpJson -Force
    }
}
