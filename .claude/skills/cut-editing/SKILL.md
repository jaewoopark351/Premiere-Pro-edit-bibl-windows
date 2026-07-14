---
name: cut-editing
description: Windows/CUDA 포팅본의 bibl_windows CLI로 영상 러프컷 자료를 생성하고 검수한다. STT, 무음/반복/false-start/filler 후보, FCP7 XML, SRT/VTT/ASS, HTML 리포트, clean WAV, transcript/export/diff, Claude workspace 브리핑을 만든다. "컷편집", "무음제거", "러프컷", "자동 편집" 요청 시 사용.
---

# 컷편집 실행

현재 Windows 포팅본의 권위 있는 실행 경로는 `engine/auto_cut.py`가 아니라 `src/bibl_windows` 패키지다. 원본 macOS 명령(`python3 engine/*.py`, `edit.sh`)을 그대로 사용하지 않는다. CUDA 실패 시 CPU로 몰래 전환하지 않고, 실제 긴 영상은 Windows + NVIDIA CUDA 기준으로 판단한다.

## -1단계: 환경 진단

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows doctor
.\.venv\Scripts\python.exe -B -m bibl_windows doctor --strict
```

`doctor --strict`가 실패하면 설치/FFmpeg/CUDA 문제를 먼저 보고한다. RTX 5070 Ti보다 낮은 GPU는 실패가 아니라 경고지만, OOM 위험을 명시한다.

## 0단계: dry-run

무거운 STT를 돌리기 전에 입력, 도구, 예상 산출물을 확인한다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard --dry-run
```

## 실행

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard
```

기본 실행은 원본 정책에 맞춰 clean WAV와 natural 오디오 프리셋을 생성한다. 끄고 싶을 때만:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard --no-clean-wav
```

PowerShell 래퍼:

```powershell
.\run.ps1 -InputPath "원본영상.mp4" -Preset standard -DryRun
.\run.ps1 -InputPath "원본영상.mp4" -Preset standard
```

## 현재 산출물

- `output\<base>_transcript.json` — Transformers Whisper 전사 결과
- `output\<base>_stt_audio.wav` — STT용 추출 오디오
- `output\<base>_cut_candidates.json` — 무음/반복/false-start 기반 후보
- `output\<base>_cut.xml` — Premiere Pro에서 가져올 FCP7 XML
- `output\<base>_cut.srt/.vtt/.ass` — 컷 타임라인 기준 자막
- `output\<base>_cut_emphasis.ass` — 강조 ASS
- `output\<base>_report.html` — HTML 후보 리포트
- `output\<base>_keep_ranges.json` — 삭제/유지 구간
- `output\<base>_cut_review.json` — 삭제/검토 후보 요약
- `output\<base>_edit_diff.json/.md` — 편집 전후 diff
- `output\<base>_transcript.md/.txt/.csv` — transcript export
- `output\<base>_manifest.json` — 실행 메타데이터
- `output\<base>_cut_audio.wav` — 기본 생성되는 정리 WAV
- `output\_workspace\<base>\00_claude_context.md` — Claude agent/skill 브리핑
- `output\_workspace\<base>\30_cut_result.md` — 컷편집가 검수용 결과 요약
- `output\_workspace\<base>\99_director_handoff.md` — 디렉터 핸드오프 초안

## 현재 제한

- 원본의 `mlx-whisper` 대신 Transformers Whisper + PyTorch CUDA를 사용한다.
- Premiere Pro GUI import/render는 자동 검증 완료라고 말하지 않는다. 실제 Premiere에서 수동 확인해야 한다.
- 내용 컷(`_content_cuts.json`)은 Claude 리서처가 제안/작성하는 단계이며, 엔진 자동 반영 여부는 별도 구현 상태를 확인한다.
- 완성 MP4 렌더링은 기본 러프컷 파이프라인의 목표가 아니다. Premiere Pro에서 XML/SRT를 가져온 뒤 최종 내보내기를 한다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\python.exe -B -m bibl_windows doctor --strict
```

Premiere Pro에서는 `output\<base>_cut.xml`을 가져와 미디어 경로가 offline이 아닌지 확인한다. 자막은 `output\<base>_cut.srt`를 별도로 가져온다.
