param(
  [string]$PythonVersion = "3.12",
  [string]$TorchVersion = "2.11.0",
  [string]$TorchVisionVersion = "0.26.0",
  [string]$TorchAudioVersion = "2.11.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$VenvDir = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-PortWarning([string]$Message) {
  Write-Warning $Message
}

function Invoke-CheckedNative {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
  }
}

function Get-PythonInfo {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @()
  )
  $Probe = "import platform,sys; print(f'{sys.version_info.major}.{sys.version_info.minor}'); print(sys.version.split()[0]); print(platform.architecture()[0])"
  $Output = & $FilePath @Arguments -c $Probe
  if ($LASTEXITCODE -ne 0 -or $Output.Count -lt 3) {
    throw "Could not inspect Python executable: $FilePath $($Arguments -join ' ')"
  }
  return [pscustomobject]@{
    MajorMinor = [string]$Output[0]
    Full       = [string]$Output[1]
    Arch       = [string]$Output[2]
  }
}

function Remove-InvalidVenv {
  param([Parameter(Mandatory = $true)][string]$Reason)
  $ResolvedRoot = (Resolve-Path -LiteralPath $Root).Path
  $ResolvedVenv = if (Test-Path -LiteralPath $VenvDir) { (Resolve-Path -LiteralPath $VenvDir).Path } else { $VenvDir }
  if (-not $ResolvedVenv.StartsWith($ResolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to remove .venv because it is outside the project root: $ResolvedVenv"
  }
  Write-PortWarning "$Reason Recreating .venv."
  try {
    Remove-Item -LiteralPath $ResolvedVenv -Recurse -Force -ErrorAction Stop
  } catch {
    throw "Failed to remove invalid .venv at '$ResolvedVenv'. Close terminals/editors using it and run install.ps1 again. Original error: $($_.Exception.Message)"
  }
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Windows Python launcher 'py' was not found. Install Python 3.12 first."
}

try {
  $PythonInfo = Get-PythonInfo -FilePath "py" -Arguments @("-$PythonVersion")
} catch {
  throw "Python $PythonVersion was not found through the Windows launcher. Install 64-bit Python $PythonVersion first."
}

Write-Host "Python $($PythonInfo.Full) ($($PythonInfo.Arch))"
if ($PythonInfo.Arch -ne "64bit") {
  throw "64-bit Python is required. Detected: $($PythonInfo.Arch)"
}

if (Test-Path -LiteralPath $VenvDir) {
  if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Remove-InvalidVenv "Existing .venv has no Scripts\python.exe."
  } else {
    try {
      $ExistingVenv = Get-PythonInfo -FilePath $VenvPython
      Write-Host "Existing .venv Python: $($ExistingVenv.Full) ($($ExistingVenv.Arch))"
      if ($ExistingVenv.MajorMinor -ne $PythonVersion) {
        Remove-InvalidVenv "Existing .venv uses Python $($ExistingVenv.MajorMinor), expected $PythonVersion."
      } elseif ($ExistingVenv.Arch -ne "64bit") {
        Remove-InvalidVenv "Existing .venv is $($ExistingVenv.Arch), expected 64bit."
      }
    } catch {
      Remove-InvalidVenv "Existing .venv Python could not be inspected: $($_.Exception.Message)"
    }
  }
}

foreach ($Tool in @("ffmpeg.exe", "ffprobe.exe")) {
  $Command = Get-Command $Tool -ErrorAction SilentlyContinue
  if ($Command) {
    Write-Host "$Tool found: $($Command.Source)"
  } else {
    Write-PortWarning "$Tool was not found on PATH. Install FFmpeg and reopen PowerShell before running real media jobs."
  }
}

if (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue) {
  try {
    $GpuRows = & nvidia-smi.exe --query-gpu=name,memory.total --format=csv,noheader
    foreach ($Row in $GpuRows) {
      Write-Host "NVIDIA GPU: $Row"
    }
    $GpuText = $GpuRows -join "`n"
    if ($GpuText -notmatch "5070 Ti") {
      Write-PortWarning "This project is developed and verified for NVIDIA RTX 5070 Ti 16GB or better. Lower GPUs may hit CUDA OOM or run slowly."
    }
  } catch {
    Write-PortWarning "nvidia-smi.exe is present but GPU details could not be queried."
  }
} else {
  Write-PortWarning "nvidia-smi.exe was not found. CUDA diagnostics may fail until the NVIDIA driver is installed."
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
  Invoke-CheckedNative "py" "-$PythonVersion" "-m" "venv" $VenvDir
}
Invoke-CheckedNative $VenvPython "-m" "pip" "install" "--upgrade" "pip"
Invoke-CheckedNative $VenvPython "-m" "pip" "install" "--force-reinstall" "torch==$TorchVersion+cu128" "torchvision==$TorchVisionVersion+cu128" "torchaudio==$TorchAudioVersion+cu128" "--index-url" "https://download.pytorch.org/whl/cu128"
Invoke-CheckedNative $VenvPython "-m" "pip" "install" "-r" "requirements-windows.txt" "-c" "constraints-windows-cu128.txt"
Invoke-CheckedNative $VenvPython "-m" "pip" "install" "-e" "."
Invoke-CheckedNative $VenvPython "-m" "bibl_windows" "doctor" "--strict"
Write-Host "Installation completed."
