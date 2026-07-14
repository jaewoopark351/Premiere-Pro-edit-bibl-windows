# Premiere Pro Edit Bibl Windows

Windows 11 + NVIDIA CUDA 환경에서 말하는 영상의 러프컷 자료를 생성하는 Premiere Pro 편집 보조 도구입니다.

원본 프로젝트는 `biblcontentofficial-art/Premiere-Pro-edit-bibl`입니다. 이 저장소는 원본의 목적과 MIT 라이선스/크레딧을 보존하면서, macOS/Apple Silicon/`mlx-whisper`/shell script 흐름을 Windows PowerShell + PyTorch CUDA + Adobe Premiere Pro FCP7 XML 흐름으로 포팅한 버전입니다.

원본 저작권과 크레딧은 [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), [docs/FEATURE_PARITY_REPORT.md](docs/FEATURE_PARITY_REPORT.md)에 유지되어 있습니다.

## 대상 환경

이 프로젝트는 저사양 PC 지원 프로젝트가 아닙니다.

- Windows 11
- Python 3.12 64-bit 권장
- NVIDIA CUDA PyTorch
- 개발 및 검증 기준: NVIDIA RTX 5070 Ti 16GB 이상
- RAM 32GB 이상, 64GB 권장
- `ffmpeg.exe`, `ffprobe.exe` 필수
- 기본 STT 모델: `openai/whisper-large-v3`
- Adobe Premiere Pro에서 FCP7 XML/SRT를 수동 import

GPU가 RTX 5070 Ti 16GB보다 낮아도 설치를 강제로 막지는 않습니다. 다만 CUDA 메모리 부족이나 처리 속도 저하가 발생할 수 있습니다. 이 포트는 Whisper 모델을 자동으로 turbo나 소형 모델로 낮추지 않습니다.

## 현재 구현 상태

완전 구현 또는 기본 사용 가능:

- Transformers Whisper 기반 한국어 STT
- 입력 파일/모델/언어/제한 시간이 일치할 때 transcript cache 재사용
- 한국어 verbatim prompt와 previous-text conditioning 전달
- 타임스탬프 없는 STT 단어의 0초 배치 방지
- 무음/반복/false-start/짧은 발화 기반 컷 후보 생성
- aggressive 프리셋의 필러, hesitation, acoustic filler, false-start 자동 삭제 정책
- keep range 생성
- FCP7 XML 생성
- Premiere용 Windows `file://` media URI 생성
- SRT, VTT, ASS, 강조 ASS 생성
- transcript Markdown/TXT/CSV export
- edit diff JSON/Markdown
- HTML 리포트
- 버린 컷 검토 JSON과 rejected-review FCP7 XML
- 기본 clean WAV 생성
- 하이패스, 컴프레서, LUFS 정규화, de-esser, `afftdn` 노이즈 제거
- clean WAV 생성 시 전후 loudnorm 측정 sidecar
- `natural`, `podcast` 오디오 프리셋
- 노이즈 플로어 측정
- 숨소리 후보 감지 및 clean WAV에서 감쇠
- 영상 분석과 자동 프리셋 추천
- 폴더 일괄 처리
- 쇼츠용 세로 FCP7 XML, 선택적 MP4 렌더
- 2카메라 오디오 동기화
- explicit offset 기반 multicam XML
- switch interval 기반 자동 카메라 전환 XML
- Premiere XML/SRT import 및 선택적 export JSX 생성
- Premiere Pro 실행기 진입점
- `.claude` agent/skill 본문 인식, Claude Code용 workspace 브리핑/컷결과/핸드오프 자동 생성

부분 구현 또는 검토용 구현:

- 음향 기반 필러 감지는 standard/conservative에서는 review 후보이고, aggressive에서는 자동 삭제 후보입니다.
- 문장 끝 보호는 자동 삭제 후보 전체의 단어 경계에 적용됩니다.
- standard/conservative의 false-start와 필러 후보는 보수적으로 review 중심이고, aggressive에서는 원본처럼 자동 삭제 정책을 적용합니다.
- shorts MP4 렌더는 선택 기능이며 NVENC/FFmpeg 환경에 좌우됩니다.
- 자동 카메라 전환은 keep range를 일정 간격으로 나누는 보수적 round-robin 휴리스틱입니다.
- Premiere 자동 렌더링은 JSX 스크립트/실행기 제공 범위이며 Premiere 내부 실행 결과는 수동 검증이 필요합니다.

미구현:

- 원본 macOS `edit.sh`, `batch.sh`, `mlx-whisper` 경로
- 원본의 모든 세부 휴리스틱과 동일한 자동 컷 판단

## 설치

PowerShell 실행 정책 때문에 `.ps1` 실행이 막히면, 현재 세션에서만 우회해서 실행합니다.

```powershell
cd C:\Vtuber_Souorce_Code\Claude\Premiere-Pro-edit-bibl-windows
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

설치 스크립트는 다음을 확인합니다.

- Windows Python launcher `py`
- Python 3.12 64-bit
- 기존 `.venv` Python 버전/64-bit 여부
- FFmpeg/FFprobe PATH
- NVIDIA GPU와 VRAM 정보
- CUDA PyTorch cu128 패키지
- `constraints-windows-cu128.txt` 기반 Windows 의존성
- 설치 마지막의 `doctor --strict` 필수 조건

수동 설치:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install --force-reinstall "torch==2.11.0+cu128" "torchvision==0.26.0+cu128" "torchaudio==2.11.0+cu128" --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt -c constraints-windows-cu128.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

설치 확인:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor --strict
```

`doctor`는 진단 정보를 출력하고 호환성을 위해 가능한 한 종료 코드 0을 유지합니다.
`doctor --strict`는 `ffmpeg.exe`, `ffprobe.exe`, PyTorch import, CUDA 사용 가능 여부가
빠져 있으면 설치 실패로 간주합니다. GPU가 RTX 5070 Ti보다 낮은 것은 실패가 아니라
경고/권장 사양 문제로만 취급합니다.

## FFmpeg 설치

`ffmpeg.exe`와 `ffprobe.exe`가 PATH에 있어야 합니다.

```powershell
ffmpeg.exe -version
ffprobe.exe -version
```

Winget 예시:

```powershell
winget install Gyan.FFmpeg
```

설치 후 새 PowerShell을 열어 PATH를 다시 읽게 하세요.

## 실행

dry-run:

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard -DryRun
```

전체 실행:

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard
```

30초 스모크 테스트:

```powershell
.\run.ps1 -InputPath ".\input\my_video.mp4" -Preset standard -SmokeSeconds 30
```

직접 Python CLI:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run ".\input\my_video.mp4" --preset standard
```

중요 옵션:

- `--limit-seconds N` / `-LimitSeconds N`: STT, 무음 분석, 컷 후보, XML, 자막, 리포트 전체를 첫 N초로 제한합니다.
- `--smoke-seconds N` / `-SmokeSeconds N`: `--limit-seconds`와 같은 전체 파이프라인 스모크 제한입니다.
- `--stt-limit-seconds N` / `-SttLimitSeconds N`: Whisper에 넣는 WAV만 N초로 제한합니다.
- `--stt-batch-size 1`: RTX 5070 Ti 기준 기본 안전값입니다.
- `--stt-chunk-seconds 25`: VRAM 점유를 조금 낮추려면 22~25 사이로 조정합니다.
- `--no-clean-wav` / `-NoCleanWav`: 원본 기본 동작과 달리 clean WAV 생성을 끕니다.
- `--output-dir NAME`: `output\NAME\...` 아래에 생성합니다.
- `--output-name NAME`: 산출물 기본 이름을 직접 지정합니다.
- `--overwrite`: 같은 이름 manifest가 있어도 기존 base name을 재사용합니다.
- `--no-transcript-cache` / `-NoTranscriptCache`: 조건이 일치하는 기존 transcript JSON이 있어도 Whisper를 다시 실행합니다.
- `--debug`: Python traceback을 표시합니다. 평소에는 짧은 오류 메시지만 출력합니다.

## 출력 파일

기본 출력 위치는 `output` 폴더입니다.

- `*_transcript.json`: Whisper 전사 결과
- `*_stt_audio.wav`: STT 입력용 16kHz mono WAV
- `*_cut_candidates.json`: 컷 후보와 review 데이터
- `*_keep_ranges.json`: 유지 구간
- `*_cut_review.json`: 삭제 구간, review 후보, 촘촘한 컷 구간 요약
- `*_rejected.xml`: 버린 컷만 이어 붙인 Premiere 검토용 FCP7 XML
- `*_cut.xml`: Premiere Pro import용 FCP7 XML
- `*_cut.srt`: 컷 타임라인 기준 SRT
- `*_cut.vtt`: VTT
- `*_cut.ass`: ASS
- `*_cut_emphasis.ass`: 강조 ASS
- `*_transcript.md`, `*_transcript.txt`, `*_transcript.csv`: transcript export
- `*_edit_diff.json`, `*_edit_diff.md`: 편집 전후 diff
- `*_report.html`: HTML 리포트
- `*_cut_audio.wav`: 기본 생성되는 정리 WAV
- `*_audio_loudness.json`: 원본/clean WAV loudnorm 측정값
- `*_manifest.json`: 실행 메타데이터
- `_workspace\<base>\00_claude_context.json/.md`: Claude Code agent/skill 브리핑과 실제 산출물 맵
- `_workspace\<base>\30_cut_result.md`: 컷편집가 검수용 결과 요약
- `_workspace\<base>\99_director_handoff.md`: Premiere 수동 검증과 후속 agent 작업용 핸드오프 초안

서로 다른 폴더의 같은 파일명 입력이 기존 manifest와 충돌하면, 기본 산출물 이름 뒤에 짧은 경로 해시가 붙습니다.

## Claude Code 연동

원본 프로젝트는 `.claude/agents`와 `.claude/skills`를 Claude Code 편집팀의 작업 지침으로 사용합니다. Windows 포팅본도 같은 구조를 유지하되, macOS `engine/*.py` 명령 대신 `bibl_windows` CLI와 현재 Windows 산출물명을 기준으로 동작하도록 정리했습니다.

파이프라인을 실행하면 `output\_workspace\<base>\` 아래에 Claude가 바로 읽을 수 있는 파일을 만듭니다.

- `00_claude_context.md`: 입력 영상, 실행 옵션, 생성 파일, agent/skill 목록, 다음 작업 순서
- `30_cut_result.md`: STT/컷 후보/검수 대상 파일 요약
- `99_director_handoff.md`: Premiere import 파일과 수동 검증 체크리스트

`.claude` 자산 자체를 확인하려면:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli claude --full --include-body --output .\output\claude_assets.json
```

`--include-body`는 agent/skill Markdown 본문까지 JSON에 포함합니다. 일반 상태 확인이나 doctor에서는 요약만 사용합니다.

## Premiere Pro에서 불러오기

1. Premiere Pro를 엽니다.
2. `File > Import`를 선택합니다.
3. `output\*_cut.xml`을 가져옵니다.
4. 같은 폴더의 `*_cut.srt`, `*_cut.ass` 등을 필요한 자막 트랙으로 import합니다.
5. XML의 media path가 원본 영상을 가리키는지 확인합니다.
6. 컷과 자막을 수동 검토한 뒤 Premiere에서 최종 렌더링합니다.

로컬 드라이브 경로는 Premiere Pro 2024에서 수동 검증된 FCP7 형식인 `file:C:/Videos/clip.mp4`로 생성됩니다.
표준 `file:///C:/...` URI는 Premiere가 `\\C:\...` 형태의 깨진 경로로 해석할 수 있어 기본값으로 쓰지 않습니다.
네트워크 UNC 경로는 `file://NAS/share/...` 형식으로 생성됩니다. Premiere 환경에서 UNC import가 불안정하면 네트워크 공유를 드라이브 문자로 매핑한 뒤 실행하세요.

XML import 시 Premiere Pro가 미디어 연결 창을 띄우면 먼저 XML의 pathurl이 실제 파일로 복원되는지 검사합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli validate-xml ".\output\my_video_cut.xml" --media ".\input\my_video.mp4" --clean-audio ".\output\my_video_cut_audio.wav"
```

경로 인코딩/URI 형식을 비교하려면 같은 영상의 1초짜리 최소 재현 XML을 여러 변형으로 생성합니다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli premiere-path-tests ".\input\my_video.mp4"
```

생성되는 `*_literal_path_test.xml`, `*_encoded_path_test.xml`, `*_legacy_drive_literal_path_test.xml`,
`*_legacy_drive_encoded_path_test.xml`, `*_localhost_literal_path_test.xml`, `*_localhost_encoded_path_test.xml`,
`*_localhost_colon_encoded_path_test.xml`을 Premiere Pro에 각각 import해서 어느 쪽이 자동 연결되는지 확인합니다.
`*_literal_path_test.xml`은 기본 정책인 `file:C:/...` 리터럴 경로를 사용합니다. 나머지는 표준 URI,
`file://C:/...`, `file://localhost/...` 회귀 비교용입니다. 자동 테스트는 파일 존재와 URI 복원까지 검증하지만
Premiere GUI import 성공은 수동 검증 항목입니다.

## 추가 명령

영상 분석:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli analyze-video ".\input\my_video.mp4" --print
```

프리셋 추천:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli recommend-preset ".\input\my_video.mp4"
```

쇼츠 XML:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli shorts ".\input\my_video.mp4" "00:12-00:28" --transcript ".\output\my_video_transcript.json"
```

2카메라 동기화:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli sync-2cam ".\input\cam_a.mp4" ".\input\cam_b.mp4"
```

multicam XML:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli multicam-xml ".\input\master.mp4" --camera ".\input\cam_b.mp4" 1.25 --keep-ranges ".\output\master_keep_ranges.json"
```

자동 카메라 전환 XML:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli auto-multicam-xml ".\input\master.mp4" --camera ".\input\cam_b.mp4" 1.25 --keep-ranges ".\output\master_keep_ranges.json" --switch-interval 6
```

Premiere import/export JSX 생성:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli premiere-script ".\output\my_video_cut.xml" --srt ".\output\my_video_cut.srt" --output my_video_premiere_import.jsx --export-mp4 my_video_premiere_export.mp4
```

Premiere 실행:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli premiere-launch --script ".\output\my_video_premiere_import.jsx"
```

Windows용 Premiere Pro는 After Effects의 `-r script.jsx` 같은 명령줄 JSX 자동 실행 스위치를 지원하지 않습니다. 따라서 `premiere-launch --script`는 스크립트 파일 존재 여부를 확인하고 Premiere만 실행한 뒤 수동 실행 안내를 출력합니다. 새 프로젝트를 만든 뒤 `File > Import`로 `*_cut.xml`과 자막을 직접 가져오거나, 사용 중인 Premiere 버전에 스크립트 실행 메뉴가 있으면 생성된 JSX를 Premiere 내부에서 실행하세요.

폴더 일괄 처리:

```powershell
powershell -ExecutionPolicy Bypass -File .\batch.ps1 -InputDirectory ".\input" -Preset standard
```

`batch.ps1`은 파일 하나가 실패해도 나머지를 계속 처리하고, 마지막에 성공/실패 목록을 출력합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

현재 테스트에는 Windows URI, 한글/공백/특수문자 경로, UNC URI, FCP7 XML pathurl 복원/파일 존재 검증, output collision, 전체 pipeline limit 전달, aggressive 자동 삭제 정책, 기본 clean WAV/natural, STT prompt/timestamp 처리, transcript cache, rejected XML/review JSON, CLI 오류 메시지, FCP7 XML 파싱, mocked STT E2E가 포함됩니다.

## 알려진 제한

- Premiere Pro GUI import와 최종 렌더링은 수동 검증이 필요합니다.
- XML/SRT 생성은 자동 테스트하지만 Premiere 내부 해석 결과까지 자동 보장하지는 않습니다.
- 자동 카메라 전환은 휴리스틱 기반이므로 컷마다 사람이 최종 확인해야 합니다.
- Premiere 자동 렌더링은 JSX 생성까지 제공합니다. Windows Premiere Pro는 명령줄 JSX 자동 실행을 지원하지 않아 `premiere-launch --script`는 Premiere만 열고 수동 실행 안내를 출력합니다.
- STT 정확도와 컷 품질은 영상 음질, 배경음악, 발화 스타일에 따라 달라집니다.
- source video는 수정하지 않습니다. 모든 산출물은 `output` 아래에 생성됩니다.
