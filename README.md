# Premiere Pro Edit Bibl Windows

Windows와 NVIDIA CUDA 환경에서 말하는 영상의 러프컷 자료를 만드는 Premiere Pro 편집 보조 도구입니다.

원본 오픈소스 `Premiere-Pro-edit-bibl`은 macOS/Apple Silicon/`mlx-whisper`/`edit.sh` 중심 프로젝트입니다. 이 저장소는 그 목적을 Windows에서 쓰기 위해 다시 구성한 포팅본입니다. 따라서 README의 명령은 Windows PowerShell 기준이며, 원본과 1:1로 완전히 같은 기능을 제공한다고 보지 않아야 합니다.

## 무엇을 해주나요

입력 영상 1개를 받아 다음 산출물을 만듭니다.

- Whisper 계열 STT 전사 JSON
- 무음, 반복, false-start, 짧은 발화 기반 컷 후보 JSON
- Premiere Pro에서 가져올 수 있는 FCP7 XML 러프컷
- 컷 타임라인에 맞춘 SRT 자막
- HTML 리포트
- 실행 메타데이터 manifest
- 선택 시 정리된 WAV 오디오

중요: 현재 버전은 완성 MP4를 바로 렌더링하지 않습니다. 결과물은 `output\*_cut.xml`이며, Premiere Pro에서 XML을 가져온 뒤 사용자가 최종 확인과 내보내기를 합니다.

## 현재 지원 범위

지원합니다.

- Windows 11 기준 실행
- NVIDIA CUDA PyTorch 사용
- ffmpeg/ffprobe 기반 미디어 분석
- Transformers Whisper 기반 한국어 STT
- FCP7 XML 생성
- SRT 자막 생성
- HTML 리포트 생성
- `.claude\agents`, `.claude\skills` 프로젝트 자산 인식
- PowerShell 래퍼 `install.ps1`, `run.ps1`, `batch.ps1`

아직 원본과 동일하다고 볼 수 없는 영역입니다.

- 원본 `engine\auto_cut.py`의 모든 세부 로직
- macOS용 `mlx-whisper`
- `edit.sh`, `batch.sh`
- 쇼츠 자동 제작
- 멀티캠 자동 편집
- 강조 자막 ASS 고급 생성
- Premiere Pro에서 자동 렌더링까지 완료하는 기능

## 폴더 구조

```text
Premiere-Pro-edit-bibl-windows\
  .claude\                 Claude/Codex용 agents, skills
  config\                  컷 프리셋 JSON
  input\                   입력 영상을 두기 좋은 폴더
  output\                  실행 결과물
  src\bibl_windows\        Windows 포팅본 Python 코드
  tests\                   테스트
  install.ps1              Windows 설치 스크립트
  run.ps1                  단일 영상 실행 스크립트
  batch.ps1                폴더 일괄 처리 스크립트
  requirements-windows.txt Windows 의존성
```

## 요구 사항

필수:

- Windows 11 권장
- Python 3.12 권장
- `ffmpeg.exe`, `ffprobe.exe`
- NVIDIA GPU 권장
- Adobe Premiere Pro

Python 버전:

- 권장: Python 3.12
- 허용: Python 3.10 이상, 3.13 미만
- Python launcher `py`가 설치되어 있으면 `install.ps1`이 편합니다.

GPU:

- 권장: NVIDIA GPU + CUDA PyTorch
- CPU도 `--allow-cpu-fallback`으로 실행할 수 있지만 매우 느릴 수 있습니다.

ffmpeg:

- `ffmpeg.exe`와 `ffprobe.exe`가 PATH에 있어야 합니다.
- 설치 후 아래 명령이 PowerShell에서 동작해야 합니다.

```powershell
ffmpeg.exe -version
ffprobe.exe -version
```

## 처음 설치

PowerShell을 열고 프로젝트 폴더로 이동합니다.

```powershell
cd C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows
```

설치 스크립트를 실행합니다.

```powershell
.\install.ps1
```

`install.ps1`이 하는 일:

- `.venv` 가상환경 생성
- pip 업그레이드
- CUDA 12.8용 PyTorch 설치
- Windows 의존성 설치
- 현재 프로젝트 editable 설치
- `doctor` 진단 실행

설치가 끝나면 아래 명령으로 상태를 다시 확인합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

정상이라면 대략 이런 정보를 볼 수 있습니다.

```text
ffmpeg path
ffprobe path
torch_available: true
cuda_available: true
gpu_name: ...
claude.exists: true
```

## 수동 설치

`install.ps1`을 쓰지 않고 직접 설치하려면 아래 순서대로 실행합니다.

```powershell
cd C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

CPU-only torch가 설치되면 CUDA가 잡히지 않습니다. 이때는 PyTorch CUDA wheel을 다시 설치합니다.

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

## 빠른 동작 확인

테스트를 실행합니다.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

현재 기준 정상 결과 예시:

```text
22 passed
```

`.claude` 프로젝트 자산 인식도 확인합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude
```

정상 예시:

```json
{
  "exists": true,
  "agent_count": 6,
  "skill_count": 7
}
```

상세 JSON이 필요하면 파일로 저장합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude --full --output output\claude_full_ascii.json --ascii-output
Get-Content .\output\claude_full_ascii.json
```

`\uc601\uc0c1` 같은 표기는 깨진 것이 아닙니다. PowerShell 인코딩 문제를 피하기 위한 JSON Unicode escape입니다. JSON으로 읽으면 원래 한글로 복원됩니다.

## 입력 영상 준비

가장 단순한 방법은 `input` 폴더에 영상 파일을 넣는 것입니다.

예시:

```text
C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows\input\my_video.mp4
```

지원 확장자는 주로 `mp4`, `mov`, `m4v`, `mkv`입니다. ffmpeg가 읽을 수 있는 영상이면 대부분 처리 가능합니다.

## 30초 스모크 테스트

긴 영상 전체를 돌리기 전에 30초만 먼저 확인합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\test.mp4.mp4" --limit-seconds 30 --allow-cpu-fallback
```

PowerShell 래퍼를 쓰는 방법:

```powershell
.\run.ps1 -InputPath ".\input\test.mp4.mp4" -Preset standard -LimitSeconds 30 -AllowCpuFallback
```

GPU가 정상이라면 `--allow-cpu-fallback`이나 `-AllowCpuFallback`은 없어도 됩니다. 다만 모델이나 CUDA 문제로 실패할 때 임시 확인용으로 붙일 수 있습니다.

## 실제 영상 전체 실행

Python CLI:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\my_video.mp4" --preset standard
```

PowerShell 래퍼:

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard
```

정리 WAV까지 만들려면 `--clean-wav` 또는 `-CleanWav`를 붙입니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\my_video.mp4" --preset standard --clean-wav
```

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard -CleanWav
```

## 프리셋

프리셋은 `config` 폴더에 있습니다.

```text
config\conservative.json
config\standard.json
config\aggressive.json
```

선택 기준:

- `conservative`: 적게 자름. 자연스러움 우선.
- `standard`: 기본값. 대부분의 테스트와 일반 영상에 권장.
- `aggressive`: 더 많이 자름. 결과 확인과 수동 보정 필요.

사용 예:

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset conservative
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset aggressive
```

## 일괄 처리

폴더 안의 영상들을 순서대로 처리합니다.

```powershell
.\batch.ps1 -InputDirectory ".\input" -Preset standard
```

30초씩만 테스트:

```powershell
.\batch.ps1 -InputDirectory ".\input" -Preset standard -LimitSeconds 30
```

정리 WAV 포함:

```powershell
.\batch.ps1 -InputDirectory ".\input" -Preset standard -CleanWav
```

## 명령어 목록

진단:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

`.claude` 자산 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude
```

미디어 정보 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli probe ".\input\my_video.mp4"
```

전사만 실행:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli transcribe ".\input\my_video.mp4" --preset standard --limit-seconds 30
```

컷 후보 분석:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli analyze-cuts ".\input\my_video.mp4" --preset standard --transcript ".\output\my_video_transcript.json"
```

이미 만든 후보와 전사 JSON으로 XML/SRT만 export:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli export ".\input\my_video.mp4" --preset standard --candidates ".\output\my_video_cut_candidates.json" --transcript ".\output\my_video_transcript.json"
```

전체 파이프라인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\my_video.mp4" --preset standard
```

## 산출물

모든 결과는 `output` 폴더에 생성됩니다.

예를 들어 입력 파일이 `my_video.mp4`라면:

```text
output\my_video_transcript.json        STT 전사 결과
output\my_video_stt_audio.wav          전체 실행 STT용 오디오
output\my_video_stt_30s.wav            제한 실행 STT용 오디오
output\my_video_cut_candidates.json    컷 후보
output\my_video_cut.xml                Premiere Pro 가져오기용 FCP7 XML
output\my_video_cut.srt                컷 타임라인 기준 자막
output\my_video_report.html            컷 리포트
output\my_video_keep_ranges.json       유지 구간/삭제 구간
output\my_video_cut_audio.wav          선택 시 생성되는 정리 WAV
output\my_video_manifest.json          실행 메타데이터
```

가장 중요한 파일은:

```text
output\my_video_cut.xml
output\my_video_cut.srt
output\my_video_report.html
```

## Premiere Pro에서 열기

1. Premiere Pro를 엽니다.
2. 새 프로젝트를 만들거나 기존 프로젝트를 엽니다.
3. `파일 > 가져오기`를 선택합니다.
4. `output\my_video_cut.xml`을 가져옵니다.
5. 생성된 시퀀스를 열어 컷을 확인합니다.
6. 필요하면 `output\my_video_cut.srt`도 자막으로 가져옵니다.
7. 컷이 어색한 부분은 Premiere에서 직접 조정합니다.
8. 최종 MP4는 Premiere Pro에서 내보내기 합니다.

현재 Python 도구는 MP4 렌더링까지 하지 않습니다. XML은 편집 지시서이고, 실제 완성 영상은 Premiere Pro에서 내보냅니다.

## PowerShell 주의 사항

명령은 한 줄씩 실행하세요.

좋은 예:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude
.\.venv\Scripts\python.exe -B -m pytest -q
```

`>>`가 보이면 PowerShell이 여러 줄 입력 모드에 들어간 것입니다. 이전 줄에서 따옴표나 괄호가 닫히지 않았거나, 여러 명령을 한 번에 붙여넣은 경우가 많습니다. `Ctrl+C`로 빠져나온 뒤 한 줄씩 다시 실행하세요.

한글 출력이 깨질 때:

- 기본 확인은 `claude` 요약 출력만 사용하세요.
- 상세 JSON은 `--ascii-output`을 쓰세요.
- `\uc601\uc0c1` 같은 문자열은 JSON Unicode escape이며 정상입니다.

## 자주 발생하는 문제

### ffmpeg를 찾을 수 없음

증상:

```text
ffmpeg.exe was not found on PATH.
```

해결:

- ffmpeg를 설치합니다.
- `ffmpeg.exe`와 `ffprobe.exe`가 PATH에 있는지 확인합니다.

```powershell
ffmpeg.exe -version
ffprobe.exe -version
```

### CUDA가 안 잡힘

증상:

```text
cuda_available: false
```

해결:

```powershell
.\.venv\Scripts\python.exe -m pip install --force-reinstall torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

그래도 안 되면 GPU 드라이버와 CUDA 지원 상태를 확인하세요.

### 모델 다운로드 경고

처음 Whisper 모델을 사용할 때 Hugging Face 모델 파일을 내려받을 수 있습니다. 네트워크나 캐시 상태에 따라 시간이 걸릴 수 있습니다.

다음 경고는 실패가 아니라 안내일 수 있습니다.

```text
Warning: You are sending unauthenticated requests to the HF Hub.
```

### 입력 파일이 없다고 나옴

증상:

```text
Input media file was not found
```

해결:

- 예시 경로를 그대로 쓰지 마세요.
- 실제 파일 경로를 넣으세요.
- 경로에 공백이 있으면 따옴표로 감싸세요.

```powershell
.\run.ps1 -InputPath "C:\Users\me\Videos\recording.mp4"
```

### XML은 있는데 MP4가 없음

정상입니다. 이 도구는 Premiere Pro에서 가져올 XML과 SRT를 만듭니다. 완성 MP4는 Premiere Pro에서 내보내야 합니다.

## Claude/Codex를 위한 프로젝트 메모

이 섹션은 Claude, Codex, 다른 AI 코딩 에이전트가 프로젝트를 빠르게 이해하도록 작성되었습니다.

### 프로젝트 정체성

- 이 저장소는 원본 `Premiere-Pro-edit-bibl`의 Windows/NVIDIA CUDA 포팅본입니다.
- 원본 macOS README의 `edit.sh`, `mlx-whisper`, `engine\*.py` 전체 기능을 그대로 실행하는 프로젝트가 아닙니다.
- 현재 권위 있는 실행 경로는 `src\bibl_windows` 패키지와 PowerShell 래퍼입니다.
- 사용자는 Premiere Pro에서 가져올 수 있는 러프컷 XML/SRT를 원합니다.
- 완성 MP4 자동 렌더링을 지원한다고 말하지 마세요.

### 가장 중요한 명령

상태 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

`.claude` 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude
```

테스트:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

30초 스모크 테스트:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\test.mp4.mp4" --limit-seconds 30 --allow-cpu-fallback
```

실제 실행:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\my_video.mp4" --preset standard
```

### `.claude` 자산

현재 프로젝트는 다음을 읽습니다.

```text
.claude\agents\*.md
.claude\skills\*\SKILL.md
```

확인 명령:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude
```

상세 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude --full --output output\claude_full_ascii.json --ascii-output
```

실행 manifest에도 `.claude` 요약 정보가 들어갑니다.

### 코드 흐름

핵심 엔트리:

```text
src\bibl_windows\cli.py
src\bibl_windows\pipeline.py
src\bibl_windows\runtime.py
src\bibl_windows\claude_assets.py
```

전체 실행 흐름:

```text
CLI run
  -> RuntimeContext.discover()
  -> ffmpeg/ffprobe 확인
  -> 입력 파일 검증
  -> STT용 WAV 추출
  -> TransformersWhisperBackend.transcribe()
  -> transcript JSON 저장
  -> silence/repeat/false-start 후보 분석
  -> FCP7 XML 생성
  -> SRT 생성
  -> HTML report 생성
  -> manifest JSON 생성
```

### 산출물 의미

- `*_cut.xml`: Premiere Pro용 핵심 결과물
- `*_cut.srt`: 자막
- `*_report.html`: 사람이 확인할 리포트
- `*_manifest.json`: 실행 추적 정보
- `*_cut_audio.wav`: `--clean-wav` 사용 시 생성

### AI가 답변할 때 주의할 점

- 원본 README와 현재 Windows 포팅본을 혼동하지 마세요.
- `README.md`는 이제 Windows 포팅본 기준 문서입니다.
- 사용자가 “편집된 영상 어디 있어?”라고 물으면 MP4가 아니라 `output\*_cut.xml`이 핵심 결과라고 설명하세요.
- Premiere Pro에서 XML을 가져온 뒤 최종 MP4를 내보내야 한다고 말하세요.
- PowerShell에서 `>>`가 보이면 한 줄씩 실행하라고 안내하세요.
- 한글 JSON 출력이 깨지면 `--ascii-output`을 안내하세요.
- 테스트는 `.\.venv\Scripts\python.exe -B -m pytest -q`를 기준으로 말하세요.

## 라이선스와 원본

이 프로젝트는 원본 오픈소스를 참고해 Windows용으로 재구성한 포팅본입니다. 원본 README를 그대로 실행 문서로 쓰지 말고, 이 README와 `WINDOWS_SETUP.md`, `PORTING_REPORT.md`를 기준으로 사용하세요.
