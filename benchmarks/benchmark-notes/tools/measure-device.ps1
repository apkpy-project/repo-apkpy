param(
    [string]$Adb = "adb"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$results = Join-Path $root "results"

if (-not (Get-Command $Adb -ErrorAction SilentlyContinue)) {
    throw "adb was not found. Pass -Adb with the full executable path."
}

$apps = @(
    @{ framework = "ApkPy"; package = "com.apkpy.benchmark.apkpy"; activity = "com.apkpy.app.Screen_homeActivity" },
    @{ framework = "Flet"; package = "com.apkpy.benchmark.benchmark_notes_flet"; activity = "com.apkpy.benchmark.benchmark_notes_flet.MainActivity" },
    @{ framework = "BeeWare/Toga"; package = "com.apkpy.benchmark.benchmark_notes"; activity = "org.beeware.android.MainActivity" }
)

$runs = @()
foreach ($app in $apps) {
    foreach ($run in 1..3) {
        & $Adb shell am force-stop $app.package | Out-Null
        Start-Sleep -Milliseconds 250
        $launch = (& $Adb shell am start -W -n "$($app.package)/$($app.activity)" | Out-String)
        $time = [regex]::Match($launch, '(?m)(?:WaitTime|TotalTime):\s*(\d+)')
        Start-Sleep -Seconds 2
        $memory = (& $Adb shell dumpsys meminfo $app.package | Out-String)
        $pss = [regex]::Match($memory, 'TOTAL PSS:\s*(\d+)')
        $runs += [ordered]@{
            framework = $app.framework
            run = $run
            cold_start_ms = if ($time.Success) { [int]$time.Groups[1].Value } else { $null }
            pss_kb = if ($pss.Success) { [int]$pss.Groups[1].Value } else { $null }
        }
    }
}

$runs | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (
    Join-Path $results "device-runs-rerun.json"
)
Write-Host "Device measurements completed. No build or publish action was run."
