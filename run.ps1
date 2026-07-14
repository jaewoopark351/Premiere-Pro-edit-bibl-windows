param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [ValidateSet("conservative","standard","aggressive")][string]$Preset = "standard",
  [double]$LimitSeconds = 0,
  [Alias("TranscribeSeconds")][double]$SttLimitSeconds = 0,
  [double]$SmokeSeconds = 0,
  [int]$SttBatchSize = 1,
  [double]$SttChunkSeconds = 25,
  [ValidateSet("standard","natural","podcast")][string]$AudioPreset = "standard",
  [string]$OutputDir,
  [string]$OutputName,
  [switch]$AllowCpuFallback,
  [switch]$CleanWav,
  [switch]$NoExtraExports,
  [switch]$NoAdvancedAudioAnalysis,
  [switch]$Overwrite,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $env:PYTORCH_CUDA_ALLOC_CONF) {
  $env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
}

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe" -PathType Leaf)) {
  throw "Project virtualenv was not found. Run: powershell -ExecutionPolicy Bypass -File .\install.ps1"
}

if (-not (Test-Path -LiteralPath $InputPath -PathType Leaf)) {
  throw "Input video was not found: $InputPath"
}

$ArgsList = @("-m", "bibl_windows", "run", $InputPath, "--preset", $Preset)
$PipelineLimit = $LimitSeconds
if ($SmokeSeconds -gt 0) { $PipelineLimit = $SmokeSeconds }
if ($PipelineLimit -gt 0) { $ArgsList += @("--limit-seconds", "$PipelineLimit") }
if ($SttLimitSeconds -gt 0) { $ArgsList += @("--stt-limit-seconds", "$SttLimitSeconds") }
if ($SttBatchSize -gt 0) { $ArgsList += @("--stt-batch-size", "$SttBatchSize") }
if ($SttChunkSeconds -gt 0) { $ArgsList += @("--stt-chunk-seconds", "$SttChunkSeconds") }
if ($AudioPreset) { $ArgsList += @("--audio-preset", "$AudioPreset") }
if ($OutputDir) { $ArgsList += @("--output-dir", "$OutputDir") }
if ($OutputName) { $ArgsList += @("--output-name", "$OutputName") }
if ($AllowCpuFallback) { $ArgsList += "--allow-cpu-fallback" }
if ($CleanWav) { $ArgsList += "--clean-wav" }
if ($NoExtraExports) { $ArgsList += "--no-extra-exports" }
if ($NoAdvancedAudioAnalysis) { $ArgsList += "--no-advanced-audio-analysis" }
if ($Overwrite) { $ArgsList += "--overwrite" }
if ($DryRun) { $ArgsList += "--dry-run" }
if ($DebugPreference -ne "SilentlyContinue") { $ArgsList += "--debug" }

& .\.venv\Scripts\python.exe @ArgsList
exit $LASTEXITCODE
