# Porting Report

This report records commands actually executed, logs, generated files, test
results, and unverified items.

## Stage 1 - Source Analysis

Executed commands:

```text
Get-Location
rg --files
git status --short
Get-Content -Raw -Encoding UTF8 <source files>
rg <dependency/function searches>
New-Item -ItemType Directory -Force -Path 'C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows'
git init
git status --short
git add PORTING_PLAN.md
git commit -m "Analyze source and plan Windows port"
```

Observed logs:

```text
git status --short from source snapshot:
fatal: not a git repository (or any of the parent directories): .git

git init:
Initialized empty Git repository in C:/Vtuber_Souorce_Code/Premiere-Pro-edit-bibl-windows/.git/

git add:
warning: in the working copy of 'PORTING_PLAN.md', LF will be replaced by CRLF the next time Git touches it

git commit:
[master (root-commit) b1f4bd1] Analyze source and plan Windows port
 1 file changed, 248 insertions(+)
 create mode 100644 PORTING_PLAN.md
```

Generated files:

```text
PORTING_PLAN.md
```

## Stage 2 - Windows Minimum Runtime

Status: in progress.

Executed commands:

```text
py -0p
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip --version
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m bibl_windows doctor
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -m bibl_windows doctor
.\.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m bibl_windows doctor
New-Item -ItemType Directory -Force -Path '.\output\한글 공백 테스트'
ffmpeg.exe -hide_banner -y -f lavfi -i testsrc2=duration=12:size=1280x720:rate=30 -f lavfi -i sine=frequency=440:duration=12 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest ".\output\한글 공백 테스트\샘플 영상.mp4"
.\.venv\Scripts\python.exe -m bibl_windows probe ".\output\한글 공백 테스트\샘플 영상.mp4"
```

Observed logs:

```text
py -0p:
 -V:3.14 *        C:\Users\jaewo\AppData\Local\Python\pythoncore-3.14-64\python.exe
 -V:3.12          C:\Users\jaewo\AppData\Local\Programs\Python\Python312\python.exe

.\.venv\Scripts\python.exe --version:
Python 3.12.10

pytest:
...........                                                              [100%]

doctor after CUDA torch install:
torch_version: 2.11.0+cu128
torch CUDA version: 12.8
torch.cuda.is_available(): true
GPU: NVIDIA GeForce RTX 5070 Ti
VRAM bytes: 17094475776

ffmpeg:
ffmpeg version 8.1.2-full_build-www.gyan.dev Copyright (c) 2000-2026 the FFmpeg developers

ffprobe:
ffprobe version 8.1.2-full_build-www.gyan.dev Copyright (c) 2007-2026 the FFmpeg developers

probe on Korean/space path:
duration: 12.0
video: h264 1280x720 30.0 fps
audio: aac 44100 Hz 1 channel
```

Generated files:

```text
.venv\
output\한글 공백 테스트\샘플 영상.mp4
```

Notes:

- The first plain `pip install torch` resolved to `torch-2.13.0+cpu`; this did not satisfy the CUDA requirement.
- Reinstalling from the official PyTorch CUDA 12.8 index resolved to `torch-2.11.0+cu128` and CUDA became available.
- PowerShell displayed Korean paths from JSON output as mojibake in the captured console, but the file was created and probed successfully.

Still unverified:

- Real Korean speech STT.
- Premiere Pro import.

## Stage 3 - Transformers Whisper STT

Executed commands:

```text
Add-Type -AssemblyName System.Speech; <list installed voices>
Add-Type -AssemblyName System.Speech; <create output\한글 공백 테스트\한국어 음성 샘플.wav with Microsoft Heami Desktop>
ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1 ".\output\한글 공백 테스트\한국어 음성 샘플.wav"
ffmpeg.exe -hide_banner -y -f lavfi -i testsrc2=duration=23.5:size=1280x720:rate=30 -i ".\output\한글 공백 테스트\한국어 음성 샘플.wav" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4"
.\.venv\Scripts\python.exe -m bibl_windows transcribe ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" --seconds 23.5 --model openai/whisper-large-v3 --language ko
.\.venv\Scripts\python.exe -m pip install python-certifi-win32
.\.venv\Scripts\python.exe -m bibl_windows transcribe ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" --seconds 23.5 --model openai/whisper-large-v3 --language ko
```

Observed logs:

```text
Installed voices:
Microsoft Heami Desktop ko-KR Female Adult
Microsoft Zira Desktop en-US Female Adult

TTS WAV:
C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한글 공백 테스트\한국어 음성 샘플.wav 1036224 bytes

TTS WAV duration:
23.496100

First STT attempt:
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate

Fix attempted:
pip install python-certifi-win32

Second STT attempt:
transcript_json=C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한국어 STT 샘플 영상_transcript.json
```

STT result:

```text
backend: transformers-whisper
model: openai/whisper-large-v3
device: cuda:0
segments_count: 1
words_count: 32
validation_issues: []
```

Transcript text excerpt:

```text
안녕하세요. 이 영상은 윈도우 전용 프리미어 자동 편집 테스트입니다. 한글 경로와 공백 경로를 확인하고 단어별 타임 스탬프가 제대로 나오는지 검증합니다.
```

Word timestamp excerpt:

```text
0.00-1.00 안녕하세요.
1.00-2.02 이
2.02-2.78 영상은
2.78-3.38 윈도우
3.38-3.88 전용
```

Warnings:

```text
Unauthenticated HF Hub requests may have lower rate limits.
Hugging Face cache symlinks are degraded on this Windows machine.
Transformers warns chunk_length_s is experimental for seq2seq models.
```

Generated files:

```text
output\한국어 STT 샘플 영상_stt_sample.wav 752034 bytes
output\한국어 STT 샘플 영상_transcript.json 8598 bytes
output\한글 공백 테스트\한국어 음성 샘플.wav 1036224 bytes
output\한글 공백 테스트\한국어 STT 샘플 영상.mp4 9385777 bytes
```

## Stage 4 - Timeline Core

Implemented:

- `TimeRange`
- `TranscriptSegment`
- `TranscriptWord`
- `CutCandidate`
- `KeepRange`
- `TimelineMapper`

Executed command:

```text
.\.venv\Scripts\python.exe -m pytest -q
```

Observed logs:

```text
...........                                                              [100%]
```

Coverage in tests:

- Merge overlapping deletion ranges.
- Generate keep ranges from deletion ranges.
- Map source time to edited time.
- Drop words inside deleted ranges.
- Clamp and frame-align deletion ranges.
- SRT timestamp formatting.
- Windows file URI encoding.
- FCP7 XML URI/link/sample-rate checks.

## Stage 5 - Automatic Cut Analysis

Executed command:

```text
.\.venv\Scripts\python.exe -m bibl_windows analyze-cuts ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" --preset standard --transcript ".\output\한국어 STT 샘플 영상_transcript.json"
```

Observed logs:

```text
cut_candidates_json=C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한국어 STT 샘플 영상_cut_candidates.json
```

Candidate summary:

```text
candidate_count: 4
reason: long_silence
auto_delete: true
requires_review: false
```

Candidate excerpt:

```text
1.215873-1.919637 long_silence confidence=0.85
6.680726-7.403991 long_silence confidence=0.85
15.168027-15.894331 long_silence confidence=0.85
22.757460-23.376009 long_silence confidence=0.85
```

## Stage 6 - Premiere Outputs

Executed command:

```text
.\.venv\Scripts\python.exe -m bibl_windows export ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" --preset standard --transcript ".\output\한국어 STT 샘플 영상_transcript.json" --candidates ".\output\한국어 STT 샘플 영상_cut_candidates.json" --clean-wav
```

Observed logs:

```text
xml=C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한국어 STT 샘플 영상_cut.xml
srt=C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한국어 STT 샘플 영상_cut.srt
report=C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\output\한국어 STT 샘플 영상_report.html
```

Validation:

```text
xml_parse=ok
file_uri_snippet=file:///C:/Vtuber_Souorce_Code/Premiere-Pro-edit-bibl-windows/output/%ED%95%9C%EA%B8%80%20%EA%B3%B5%EB%B0%B1%20%ED%85%8C%EC%8A%A4%ED%8A%B8/...
has_video_audio_links=True
has_samplerate=True
```

SRT remap excerpt:

```text
1
00:00:00,000 --> 00:00:01,000
안녕하세요.

2
00:00:01,300 --> 00:00:05,733
영상은 윈도우 전용 프리미어 자동 편집 테스트입니다.
```

Deletion and keep ranges:

```text
deletions:
1.200000-1.933333
6.666667-7.400000
15.166667-15.900000
22.766667-23.366667

keeps:
0.000000-1.200000
1.933333-6.666667
7.400000-15.166667
15.900000-22.766667
23.366667-23.500000
```

Generated files:

```text
output\한국어 STT 샘플 영상_cut.srt 512 bytes
output\한국어 STT 샘플 영상_cut.xml 8180 bytes
output\한국어 STT 샘플 영상_cut_audio.wav 1036366 bytes
output\한국어 STT 샘플 영상_cut_candidates.json 1688 bytes
output\한국어 STT 샘플 영상_keep_ranges.json 641 bytes
output\한국어 STT 샘플 영상_report.html 1145 bytes
```

Premiere status:

- FCP7 XML was generated and parsed as XML.
- Windows `file:///C:/...` URI and URL-encoded Korean/space path were verified.
- Adobe Premiere Pro import is unverified and requires user verification.

## Final Verification

Executed commands:

```text
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m bibl_windows doctor
git status --short
git log --oneline --decorate -5
```

Observed logs:

```text
pytest:
...........                                                              [100%]

doctor:
ffmpeg version 8.1.2-full_build-www.gyan.dev
ffprobe version 8.1.2-full_build-www.gyan.dev
Python 3.12.10
torch 2.11.0+cu128
torch CUDA 12.8
torch.cuda.is_available(): true
GPU: NVIDIA GeForce RTX 5070 Ti
VRAM bytes: 17094475776

git status --short:
<clean output>

git log:
9e81e24 (HEAD -> master) Verify CUDA Whisper and Premiere exports
9f45757 Add Windows runtime diagnostics and timeline core
b1f4bd1 Analyze source and plan Windows port
```

Known limitations:

- Adobe Premiere Pro import was not performed by Codex and remains user verification.
- The STT test used Windows Korean TTS (`Microsoft Heami Desktop`) rather than a real OBS/VTuber recording.
- The current Transformers pipeline emits warnings about experimental `chunk_length_s` for seq2seq models; long-form production transcription should be further validated on real recordings.
- HF Hub downloads were unauthenticated and may be rate-limited.
- PowerShell captured some Python JSON path output as mojibake, while UTF-8 file contents were verified separately.

User verification required:

- Import `output\한국어 STT 샘플 영상_cut.xml` into Adobe Premiere Pro on Windows.
- Confirm the linked original media path resolves correctly.
- Confirm audio/video clip linking and cut boundaries in the Premiere timeline.
- Run the same pipeline on a real Korean OBS/VTuber source file.

## PowerShell Wrapper Fix

Issue observed by user:

```text
.\run.ps1 -Input ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" -Preset standard -TranscribeSeconds 23.5 -CleanWav
bibl-windows run: error: the following arguments are required: input
```

Cause:

- `run.ps1` used a parameter named `$Input`.
- PowerShell has an automatic `$input` variable, and variable names are case-insensitive.
- The wrapper could pass an empty value to the Python CLI.

Fix:

- Renamed the wrapper parameter from `-Input` / `$Input` to `-InputPath` / `$InputPath`.
- Updated `batch.ps1` and `WINDOWS_SETUP.md`.

## Windows-First Source Reset

Request:

```text
윈도우 전용으로 처음부터 끝까지 소스코드 갈아엎는 느낌으로 가도 되니까
전부 갈아 엎어
```

Implemented changes:

- Replaced the old CLI-driven orchestration with `WindowsEditPipeline`.
- Added `RuntimeContext` / `RuntimeTools` for Windows tool discovery.
- Added `ArtifactManifest` so every full run records input, preset, mode, command, output files, STT metadata, and cut candidate summary.
- Changed the default `run` behavior from 30-second transcription to full-media transcription.
- Kept short smoke tests explicit via `--limit-seconds` / PowerShell `-LimitSeconds`.
- Kept legacy CLI alias `--transcribe-seconds` and PowerShell alias `-TranscribeSeconds`.
- Changed STT audio extraction from sample-only naming to `_stt_audio.wav` for full runs and `_stt_<seconds>s.wav` for limited runs.
- Removed plain `torch` from `pyproject.toml` optional STT dependencies so `pip install .[stt]` does not accidentally install CPU-only torch over the CUDA wheel installed by `install.ps1`.
- Extended `batch.ps1` to pass `-LimitSeconds` and `-CleanWav`.

Executed commands:

```text
.\.venv\Scripts\python.exe -m pytest -q
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\run.ps1 -InputPath ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" -Preset standard -LimitSeconds 23.5 -CleanWav
.\.venv\Scripts\python.exe -c "<inspect output manifest>"
```

Observed logs:

```text
pytest:
..............                                                           [100%]

run.ps1:
transcript_json=...
stt_audio=...\한국어 STT 샘플 영상_stt_23.5s.wav
cut_candidates_json=...
xml=...
srt=...
report=...
clean_wav=...
keep_ranges_json=...
manifest_json=...

manifest:
mode=limited
limit_seconds=23.5
stt.device=cuda:0
stt.model=openai/whisper-large-v3
stt.words=32
stt.segments=1
stt.validation_issues=[]
```

## Windows Korean Absolute Path Fix

Issue observed by user:

```text
.\.venv\Scripts\python.exe -m bibl_windows run "C:\영상 폴더\실제 영상.mp4" --preset standard --limit-seconds 30 --clean-wav
...
Error opening input file C:\영상 폴더\실제 영상.mp4.
Error opening input files: Illegal byte sequence
```

Findings:

- The bundled sample under `output\한글 공백 테스트\...` continued to run successfully.
- The logged `C:\영상 폴더\실제 영상.mp4` path is an example-style placeholder unless a real file exists there.
- ffmpeg can still throw `Illegal byte sequence` for some non-ASCII absolute paths before it produces a useful missing-file message.

Implemented changes:

- Added an input-file existence check before invoking ffmpeg.
- Added Windows extended-length path conversion for ffmpeg/ffprobe media inputs (`\\?\C:\...`).
- Fixed `python -m bibl_windows` to return a non-zero process exit code on failures.
- Added tests for Windows native ffmpeg path conversion.

Executed commands:

```text
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m bibl_windows run "C:\영상 폴더\실제 영상.mp4" --preset standard --limit-seconds 30 --clean-wav
.\.venv\Scripts\python.exe -m bibl_windows run ".\output\한글 공백 테스트\한국어 STT 샘플 영상.mp4" --preset standard --limit-seconds 23.5 --clean-wav
```

Observed logs:

```text
pytest:
................                                                         [100%]

missing placeholder path:
Input media file was not found: C:\영상 폴더\실제 영상.mp4
Replace the example path with a real video path. For example: C:\Users\<name>\Videos\recording.mp4

existing Korean sample:
transcript_json=...
stt_audio=...
cut_candidates_json=...
xml=...
srt=...
report=...
clean_wav=...
keep_ranges_json=...
manifest_json=...
```
