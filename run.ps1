param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [ValidateSet("conservative","standard","aggressive")][string]$Preset = "standard",
  [Alias("TranscribeSeconds")][double]$LimitSeconds = 0,
  [int]$SttBatchSize = 1,
  [double]$SttChunkSeconds = 25,
  [ValidateSet("standard","natural","podcast")][string]$AudioPreset = "standard",
  [switch]$AllowCpuFallback,
  [switch]$CleanWav,
  [switch]$NoExtraExports,
  [switch]$NoAdvancedAudioAnalysis,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $env:PYTORCH_CUDA_ALLOC_CONF) {
  $env:PYTORCH_CUDA_ALLOC_CONF = "expandable_segments:True"
}

$ArgsList = @("-m", "bibl_windows", "run", $InputPath, "--preset", $Preset)
if ($LimitSeconds -gt 0) { $ArgsList += @("--limit-seconds", "$LimitSeconds") }
if ($SttBatchSize -gt 0) { $ArgsList += @("--stt-batch-size", "$SttBatchSize") }
if ($SttChunkSeconds -gt 0) { $ArgsList += @("--stt-chunk-seconds", "$SttChunkSeconds") }
if ($AudioPreset) { $ArgsList += @("--audio-preset", "$AudioPreset") }
if ($AllowCpuFallback) { $ArgsList += "--allow-cpu-fallback" }
if ($CleanWav) { $ArgsList += "--clean-wav" }
if ($NoExtraExports) { $ArgsList += "--no-extra-exports" }
if ($NoAdvancedAudioAnalysis) { $ArgsList += "--no-advanced-audio-analysis" }
if ($DryRun) { $ArgsList += "--dry-run" }

& .\.venv\Scripts\python.exe @ArgsList
