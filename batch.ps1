param(
  [Parameter(Mandatory=$true)][string]$InputDirectory,
  [ValidateSet("conservative","standard","aggressive")][string]$Preset = "standard",
  [double]$LimitSeconds = 0,
  [Alias("TranscribeSeconds")][double]$SttLimitSeconds = 0,
  [double]$SmokeSeconds = 0,
  [int]$SttBatchSize = 1,
  [double]$SttChunkSeconds = 25,
  [ValidateSet("standard","natural","podcast")][string]$AudioPreset = "standard",
  [string]$OutputDir,
  [switch]$AllowCpuFallback,
  [switch]$CleanWav,
  [switch]$NoExtraExports,
  [switch]$NoAdvancedAudioAnalysis,
  [switch]$NoTranscriptCache,
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

if (-not (Test-Path -LiteralPath $InputDirectory -PathType Container)) {
  throw "Input directory was not found: $InputDirectory"
}

$Dir = Resolve-Path -LiteralPath $InputDirectory
$Files = Get-ChildItem -LiteralPath $Dir -File | Where-Object { $_.Extension -match '^\.(mp4|mov|m4v|mkv)$' }
$Successes = @()
$Failures = @()
foreach ($File in $Files) {
  $ArgsList = @("-m", "bibl_windows", "run", $File.FullName, "--preset", $Preset)
  $PipelineLimit = $LimitSeconds
  if ($SmokeSeconds -gt 0) { $PipelineLimit = $SmokeSeconds }
  if ($PipelineLimit -gt 0) { $ArgsList += @("--limit-seconds", "$PipelineLimit") }
  if ($SttLimitSeconds -gt 0) { $ArgsList += @("--stt-limit-seconds", "$SttLimitSeconds") }
  if ($SttBatchSize -gt 0) { $ArgsList += @("--stt-batch-size", "$SttBatchSize") }
  if ($SttChunkSeconds -gt 0) { $ArgsList += @("--stt-chunk-seconds", "$SttChunkSeconds") }
  if ($AudioPreset) { $ArgsList += @("--audio-preset", "$AudioPreset") }
  if ($OutputDir) { $ArgsList += @("--output-dir", "$OutputDir") }
  if ($AllowCpuFallback) { $ArgsList += "--allow-cpu-fallback" }
  if ($CleanWav) { $ArgsList += "--clean-wav" }
  if ($NoExtraExports) { $ArgsList += "--no-extra-exports" }
  if ($NoAdvancedAudioAnalysis) { $ArgsList += "--no-advanced-audio-analysis" }
  if ($NoTranscriptCache) { $ArgsList += "--no-transcript-cache" }
  if ($Overwrite) { $ArgsList += "--overwrite" }
  if ($DryRun) { $ArgsList += "--dry-run" }
  if ($DebugPreference -ne "SilentlyContinue") { $ArgsList += "--debug" }
  try {
    & .\.venv\Scripts\python.exe @ArgsList
    if ($LASTEXITCODE -ne 0) {
      throw "bibl_windows.cli exited with code $LASTEXITCODE"
    }
    $Successes += $File.FullName
  } catch {
    $Failures += [pscustomobject]@{
      File = $File.FullName
      Error = $_.Exception.Message
    }
    Write-Warning "Failed: $($File.FullName) :: $($_.Exception.Message)"
  }
}

Write-Host ""
Write-Host "Batch success count: $($Successes.Count)"
foreach ($Success in $Successes) {
  Write-Host " + $Success"
}

if ($Failures.Count -gt 0) {
  Write-Host ""
  Write-Host "Batch completed with $($Failures.Count) failure(s):"
  foreach ($Failure in $Failures) {
    Write-Host " - $($Failure.File): $($Failure.Error)"
  }
  throw "Batch completed with $($Failures.Count) failure(s)."
}

exit 0
