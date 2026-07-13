param(
  [Parameter(Mandatory=$true)][string]$InputDirectory,
  [ValidateSet("conservative","standard","aggressive")][string]$Preset = "standard",
  [Alias("TranscribeSeconds")][double]$LimitSeconds = 0,
  [switch]$CleanWav
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Dir = Resolve-Path -LiteralPath $InputDirectory
$Files = Get-ChildItem -LiteralPath $Dir -File | Where-Object { $_.Extension -match '^\.(mp4|mov|m4v|mkv)$' }
foreach ($File in $Files) {
  $ArgsList = @("-InputPath", $File.FullName, "-Preset", $Preset)
  if ($LimitSeconds -gt 0) { $ArgsList += @("-LimitSeconds", "$LimitSeconds") }
  if ($CleanWav) { $ArgsList += "-CleanWav" }
  & .\run.ps1 @ArgsList
}
