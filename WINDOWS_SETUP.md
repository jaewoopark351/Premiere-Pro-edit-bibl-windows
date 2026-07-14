# Windows Setup

This project is a Windows-first rebuild inspired by `Premiere-Pro-edit-bibl`.

## Requirements

- Windows 11
- NVIDIA GPU with CUDA-capable PyTorch
- Python 3.12 recommended
- `ffmpeg.exe` and `ffprobe.exe` available on PATH
- Adobe Premiere Pro for manual import verification

## Install

```powershell
.\install.ps1
```

If PyTorch installs as a CPU-only build, install the CUDA wheel recommended by
the official PyTorch selector. This project currently defaults to the CUDA 12.8
wheel index:

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m bibl_windows doctor
.\.venv\Scripts\python.exe -m bibl_windows doctor --strict
```

`install.ps1` preserves an existing `.venv` only when it is the requested
64-bit Python version. If the version or architecture is wrong, it removes the
project-local `.venv` and recreates it before installing packages. The final
strict doctor check must pass before installation is reported as complete.

## Run

```powershell
.\run.ps1 -InputPath "C:\path with spaces\한국어 샘플.mp4" -Preset standard -CleanWav
```

The path must point to a real media file. Do not run the literal placeholder
`C:\영상 폴더\실제 영상.mp4` unless that file actually exists.

By default, `run.ps1` processes the whole media file. For a short smoke test,
limit transcription explicitly:

```powershell
.\run.ps1 -InputPath "C:\path with spaces\한국어 샘플.mp4" -Preset standard -LimitSeconds 30 -CleanWav
```

Batch processing:

```powershell
.\batch.ps1 -InputDirectory "C:\recordings" -Preset standard -CleanWav
.\batch.ps1 -InputDirectory "C:\recordings" -Preset standard -LimitSeconds 30
```

Premiere import is not claimed as verified until a human imports the generated
FCP7 XML in Adobe Premiere Pro.

## Direct Python CLI

This avoids PowerShell script execution policy entirely:

```powershell
.\.venv\Scripts\python.exe -m bibl_windows run "C:\path with spaces\한국어 샘플.mp4" --preset standard --limit-seconds 30 --clean-wav
```
