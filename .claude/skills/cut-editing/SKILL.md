---
name: cut-editing
description: Windows/CUDA 포팅본의 bibl_windows CLI로 영상 러프컷 자료를 생성한다. STT, 무음/반복/false-start 기반 컷 후보, FCP7 XML, SRT, HTML 리포트, 선택적 clean WAV를 만든다. "컷편집", "무음제거", "러프컷", "자동 편집" 요청 시 사용.
---

# 컷편집 실행

현재 Windows 포팅본의 권위 있는 실행 경로는 `engine/auto_cut.py`가 아니라 `src/bibl_windows` 패키지다. 원본 macOS 명령(`python3 engine/*.py`, `edit.sh`)을 그대로 사용하지 않는다.

## 0단계: dry-run

무거운 STT를 돌리기 전에 입력, 도구, 예상 산출물을 확인한다.

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard --dry-run
```

## 실행

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard
```

정리 WAV까지 만들 때:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard --clean-wav
```

CUDA가 준비되지 않은 상태에서 기능만 확인할 때:

```powershell
.\.venv\Scripts\python.exe -B -m bibl_windows.cli run "원본영상.mp4" --preset standard --limit-seconds 30 --allow-cpu-fallback
```

PowerShell 래퍼:

```powershell
.\run.ps1 -InputPath "원본영상.mp4" -Preset standard -DryRun
.\run.ps1 -InputPath "원본영상.mp4" -Preset standard -CleanWav
```

## 현재 산출물

- `output\<base>_transcript.json` — Transformers Whisper 전사 결과
- `output\<base>_stt_audio.wav` — STT용 추출 오디오
- `output\<base>_cut_candidates.json` — 무음/반복/false-start 기반 후보
- `output\<base>_cut.xml` — Premiere Pro에서 가져올 FCP7 XML
- `output\<base>_cut.srt` — 컷 타임라인 기준 SRT
- `output\<base>_report.html` — HTML 후보 리포트
- `output\<base>_keep_ranges.json` — 삭제/유지 구간
- `output\<base>_manifest.json` — 실행 메타데이터
- `output\<base>_cut_audio.wav` — `--clean-wav` 사용 시 생성

## 현재 제한

- VTT/ASS, 강조 자막, transcript Markdown export, edit diff, acoustic filler, breath reduce, 멀티캠, 쇼츠는 아직 Windows CLI에 구현되지 않았다.
- 원본의 `mlx-whisper` 대신 Transformers Whisper + PyTorch CUDA를 사용한다.
- 완성 MP4를 렌더링하지 않는다. Premiere Pro에서 XML/SRT를 가져온 뒤 최종 내보내기를 한다.

## 검증

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
.\.venv\Scripts\python.exe -B -m bibl_windows.cli doctor
```

Premiere Pro에서는 `output\<base>_cut.xml`을 가져와 미디어 경로가 offline이 아닌지 확인한다. 자막은 `output\<base>_cut.srt`를 별도로 가져온다.
