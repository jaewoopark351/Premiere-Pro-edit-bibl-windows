param(
  [Parameter(Mandatory=$true)][string]$InputDirectory,
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

$Dir = Resolve-Path -LiteralPath $InputDirectory
$Files = Get-ChildItem -LiteralPath $Dir -File | Where-Object { $_.Extension -match '^\.(mp4|mov|m4v|mkv)$' }
$Failures = @()
foreach ($File in $Files) {
  $ArgsList = @("-m", "bibl_windows", "run", $File.FullName, "--preset", $Preset)
  if ($LimitSeconds -gt 0) { $ArgsList += @("--limit-seconds", "$LimitSeconds") }
  if ($SttBatchSize -gt 0) { $ArgsList += @("--stt-batch-size", "$SttBatchSize") }
  if ($SttChunkSeconds -gt 0) { $ArgsList += @("--stt-chunk-seconds", "$SttChunkSeconds") }
  if ($AudioPreset) { $ArgsList += @("--audio-preset", "$AudioPreset") }
  if ($AllowCpuFallback) { $ArgsList += "--allow-cpu-fallback" }
  if ($CleanWav) { $ArgsList += "--clean-wav" }
  if ($NoExtraExports) { $ArgsList += "--no-extra-exports" }
  if ($NoAdvancedAudioAnalysis) { $ArgsList += "--no-advanced-audio-analysis" }
  if ($DryRun) { $ArgsList += "--dry-run" }
  try {
    & .\.venv\Scripts\python.exe @ArgsList
    if ($LASTEXITCODE -ne 0) {
      throw "bibl_windows.cli exited with code $LASTEXITCODE"
    }
  } catch {
    $Failures += [pscustomobject]@{
      File = $File.FullName
      Error = $_.Exception.Message
    }
    Write-Warning "Failed: $($File.FullName) :: $($_.Exception.Message)"
  }
}

if ($Failures.Count -gt 0) {
  Write-Host ""
  Write-Host "Batch completed with $($Failures.Count) failure(s):"
  foreach ($Failure in $Failures) {
    Write-Host " - $($Failure.File): $($Failure.Error)"
  }
  throw "Batch completed with $($Failures.Count) failure(s)."
}
