param(
  [string]$PythonVersion = "3.12",
  [string]$TorchVersion = "2.11.0",
  [string]$TorchVisionVersion = "0.26.0",
  [string]$TorchAudioVersion = "2.11.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-PortWarning([string]$Message) {
  Write-Warning $Message
}

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
  throw "Windows Python launcher 'py' was not found. Install Python 3.12 first."
}

try {
  $PythonCheck = & py "-$PythonVersion" -c "import platform,sys; print(sys.version.split()[0]); print(platform.architecture()[0])"
} catch {
  throw "Python $PythonVersion was not found through the Windows launcher. Install 64-bit Python $PythonVersion first."
}

$DetectedPythonVersion = $PythonCheck[0]
$DetectedPythonArch = $PythonCheck[1]
Write-Host "Python $DetectedPythonVersion ($DetectedPythonArch)"
if ($DetectedPythonArch -ne "64bit") {
  throw "64-bit Python is required. Detected: $DetectedPythonArch"
}

if (Test-Path -LiteralPath ".\.venv\Scripts\python.exe" -PathType Leaf) {
  $ExistingVenv = & .\.venv\Scripts\python.exe -c "import platform,sys; print(sys.version.split()[0]); print(platform.architecture()[0])"
  Write-Host "Existing .venv Python: $($ExistingVenv -join ' ')"
  if ($ExistingVenv[1] -ne "64bit") {
    Write-PortWarning "Existing .venv is not 64-bit. It will be recreated by py -$PythonVersion -m venv."
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

py -$PythonVersion -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --force-reinstall "torch==$TorchVersion+cu128" "torchvision==$TorchVisionVersion+cu128" "torchaudio==$TorchAudioVersion+cu128" --index-url https://download.pytorch.org/whl/cu128
& .\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt -c constraints-windows-cu128.txt
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m bibl_windows doctor
