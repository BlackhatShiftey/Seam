param(
    [string]$FilePath = "",

    [string[]]$ArgumentList = @(),

    [string]$Command = "",

    [ValidateRange(1, 100)]
    [int]$MaxCpuPercent = 85,

    [ValidateRange(1, 100)]
    [int]$MaxMemoryPercent = 90,

    [ValidateRange(1, 100)]
    [int]$MaxDiskPercent = 92,

    [ValidateRange(1, 100)]
    [int]$WarnCpuPercent = 75,

    [ValidateRange(1, 100)]
    [int]$WarnMemoryPercent = 82,

    [ValidateRange(1, 100)]
    [int]$WarnDiskPercent = 85,

    [ValidatePattern("^[A-Za-z]:$")]
    [string]$Disk = "C:",

    [ValidateRange(1, 60)]
    [int]$SampleSeconds = 2,

    [ValidateRange(1, 30)]
    [int]$BreachSamples = 3,

    [switch]$StopOnLimit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CpuPercent {
    $sample = (Get-Counter "\Processor(_Total)\% Processor Time").CounterSamples[0].CookedValue
    return [math]::Round([double]$sample, 2)
}

function Get-MemoryPercent {
    $os = Get-CimInstance Win32_OperatingSystem
    $totalKb = [double]$os.TotalVisibleMemorySize
    $freeKb = [double]$os.FreePhysicalMemory
    if ($totalKb -le 0) {
        return 0.0
    }
    $used = (($totalKb - $freeKb) / $totalKb) * 100.0
    return [math]::Round($used, 2)
}

function Get-DiskPercent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Drive
    )

    $disk = Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='" + $Drive + "'")
    if ($null -eq $disk -or [double]$disk.Size -le 0) {
        return 0.0
    }
    $used = (([double]$disk.Size - [double]$disk.FreeSpace) / [double]$disk.Size) * 100.0
    return [math]::Round($used, 2)
}

if ([string]::IsNullOrWhiteSpace($Command) -and [string]::IsNullOrWhiteSpace($FilePath)) {
    throw "Provide either -Command or -FilePath."
}

$displayCommand = $Command
if ([string]::IsNullOrWhiteSpace($displayCommand)) {
    $argPreview = if ($ArgumentList.Count -gt 0) { $ArgumentList -join " " } else { "" }
    $displayCommand = ("{0} {1}" -f $FilePath, $argPreview).Trim()
}

Write-Host ("[guard] starting: {0}" -f $displayCommand)
Write-Host ("[guard] warn: cpu>={0}% mem>={1}% disk({2})>={3}% | max: cpu>={4}% mem>={5}% disk>={6}% sample={7}s breach={8} stop={9}" -f $WarnCpuPercent, $WarnMemoryPercent, $Disk, $WarnDiskPercent, $MaxCpuPercent, $MaxMemoryPercent, $MaxDiskPercent, $SampleSeconds, $BreachSamples, [bool]$StopOnLimit)

if (-not [string]::IsNullOrWhiteSpace($Command)) {
    $process = Start-Process -FilePath "powershell" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command) -NoNewWindow -PassThru
} else {
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -NoNewWindow -PassThru
}
$terminatedByGuard = $false
$breachCount = 0
$maxCpuSeen = 0.0
$maxMemSeen = 0.0
$maxDiskSeen = 0.0

try {
    while (-not $process.HasExited) {
        Start-Sleep -Seconds $SampleSeconds
        $process.Refresh()
        if ($process.HasExited) {
            break
        }

        $cpu = Get-CpuPercent
        $mem = Get-MemoryPercent
        $diskPercent = Get-DiskPercent -Drive $Disk

        if ($cpu -gt $maxCpuSeen) { $maxCpuSeen = $cpu }
        if ($mem -gt $maxMemSeen) { $maxMemSeen = $mem }
        if ($diskPercent -gt $maxDiskSeen) { $maxDiskSeen = $diskPercent }

        $cpuBreached = $cpu -gt $MaxCpuPercent
        $memBreached = $mem -gt $MaxMemoryPercent
        $diskBreached = $diskPercent -gt $MaxDiskPercent
        $cpuWarn = $cpu -gt $WarnCpuPercent
        $memWarn = $mem -gt $WarnMemoryPercent
        $diskWarn = $diskPercent -gt $WarnDiskPercent

        if ($cpuWarn -or $memWarn -or $diskWarn) {
            Write-Warning ("[guard] near limit cpu={0}% mem={1}% disk={2}%" -f $cpu, $mem, $diskPercent)
        }

        if ($cpuBreached -or $memBreached -or $diskBreached) {
            $breachCount += 1
            Write-Warning ("[guard] breach {0}/{1} cpu={2}% mem={3}% disk={4}%" -f $breachCount, $BreachSamples, $cpu, $mem, $diskPercent)
        } else {
            $breachCount = 0
        }

        if ($breachCount -ge $BreachSamples) {
            if ($StopOnLimit) {
                Write-Warning ("[guard] threshold exceeded. terminating pid {0}" -f $process.Id)
                try {
                    taskkill /PID $process.Id /T /F | Out-Null
                } catch {
                    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                }
                $terminatedByGuard = $true
                break
            }
            Write-Warning "[guard] threshold exceeded. command kept running (StopOnLimit is off)."
            $breachCount = 0
        }
    }
} finally {
    if (-not $process.HasExited) {
        $process.WaitForExit()
    }
}

Write-Host ("[guard] max seen: cpu={0}% mem={1}% disk={2}%" -f $maxCpuSeen, $maxMemSeen, $maxDiskSeen)

if ($terminatedByGuard) {
    exit 98
}

exit $process.ExitCode
