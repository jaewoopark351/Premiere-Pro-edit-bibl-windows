param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [ValidateSet("conservative","standard","aggressive")][string]$Preset = "standard",
  [Alias("TranscribeSeconds")][double]$LimitSeconds = 0,
  [switch]$AllowCpuFallback,
  [switch]$CleanWav
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$ArgsList = @("-m", "bibl_windows", "run", $InputPath, "--preset", $Preset)
if ($LimitSeconds -gt 0) { $ArgsList += @("--limit-seconds", "$LimitSeconds") }
if ($AllowCpuFallback) { $ArgsList += "--allow-cpu-fallback" }
if ($CleanWav) { $ArgsList += "--clean-wav" }

& .\.venv\Scripts\python.exe @ArgsList
