# Feature Parity Report

작성일: 2026-07-14

비교 대상:

- Windows 포팅 저장소: `jaewoopark351/Premiere-Pro-edit-bibl-windows`
- 원본 저장소: `biblcontentofficial-art/Premiere-Pro-edit-bibl`
- 원본 비교 위치: `_upstream_compare_original` 읽기 전용 사본

이 보고서는 README 문구가 아니라 실제 호출 경로와 코드 동작을 기준으로 분류한다.

분류 기준:

- 완전 구현: Windows CLI 또는 파이프라인에서 기본 사용 가능하며 테스트가 있다.
- 부분 구현: 동작하지만 원본과 휴리스틱, 자동화 수준, 품질 보증 범위가 다르다.
- 검토용 구현: 자동 삭제/완성 기능이 아니라 review signal 또는 XML-first 산출물이다.
- 미구현: 현재 호출 경로가 없거나 Premiere/사용자 수동 작업이 필요하다.

## 라이선스와 크레딧

원본 저장소는 MIT License이며 저작권 표기는 `Copyright (c) 2026 비블 (@bibl_youtube)`이다. Windows 포팅 저장소는 LICENSE와 THIRD_PARTY_NOTICES.md에서 원본 출처, MIT 라이선스, Windows port contributors 고지를 함께 보존한다.

처리 원칙:

- 원본 코드를 직접 복사하거나 변형할 경우 원본 라이선스와 크레딧을 삭제하지 않는다.
- macOS 전용 `edit.sh`, `batch.sh`, `mlx-whisper`, `~/bin/ffmpeg` 경로는 Windows에 그대로 복사하지 않는다.
- 알고리즘만 참고한 Windows 재구현은 THIRD_PARTY_NOTICES.md에 출처와 개념을 남긴다.

## 실행 진입점 비교

| 항목 | 원본 | Windows 포팅 |
|---|---|---|
| 주 실행 | `edit.sh` -> `engine/auto_cut.py` | `run.ps1` 또는 `python -m bibl_windows.cli run` |
| 일괄 처리 | `batch.sh` | `batch.ps1` |
| STT | `mlx-whisper` | Transformers Whisper + PyTorch CUDA |
| Premiere 연동 | FCP7 XML 파일 생성 | FCP7 XML 파일 생성 |
| 렌더링 | Premiere 수동 렌더 | Premiere JSX 생성/실행기 제공, 실제 렌더 결과는 수동 검증 |
| Claude 자산 | `.claude` 문서 중심 | `.claude` 발견, doctor/manifest에 기록 |

## 현재 Windows 출력

- `*_transcript.json`
- `*_stt_audio.wav`
- `*_cut_candidates.json`
- `*_keep_ranges.json`
- `*_cut.xml`
- `*_cut.srt`, `*_cut.vtt`, `*_cut.ass`, `*_cut_emphasis.ass`
- `*_transcript.md`, `*_transcript.txt`, `*_transcript.csv`
- `*_edit_diff.json`, `*_edit_diff.md`
- `*_cut_review.json`
- `*_rejected.xml`
- `*_report.html`
- `*_cut_audio.wav` 선택
- `*_audio_loudness.json` 조건부
- `*_breath_ranges.json` 조건부
- `*_manifest.json`

## 기능 비교 표

| 기능 | 관련 원본 파일 | 관련 Windows 파일 | Windows 실제 호출 여부 | 분류 | 차이가 발생하는 이유 | 포팅 난이도 | 테스트 방법 |
|---|---|---|---:|---|---|---|---|
| Whisper 음성 인식 | `engine/make_subtitles.py`, `engine/auto_cut.py` | `stt/transformers_whisper.py`, `pipeline.py` | 예 | 부분 구현 | 원본은 `mlx-whisper`, Windows는 Transformers/PyTorch CUDA. transcript cache는 지원하지만 prompt 세부는 원본과 다름 | 중간 | mocked E2E, transcript cache test, 실제 STT smoke |
| 한국어 STT | `make_subtitles.py` | `cli.py`, `transformers_whisper.py` | 예 | 부분 구현 | 기본 `ko` 지정과 large-v3 CUDA 실행을 지원. 원본 prompt와 완전히 같지는 않음 | 쉬움 | Korean filename/input dry-run, 실제 STT |
| 무음 감지 | `silence_cut.py` | `ffmpeg_tools.detect_silence`, `pipeline.analyze_cuts` | 예 | 부분 구현 | FFmpeg silencedetect 기반이나 원본 keep 중심 세부와 다름 | 쉬움 | mocked E2E |
| 반복 발화 감지 | `auto_cut.py` | `analysis/cuts.py` | 예 | 부분 구현 | 단어 반복과 짧은 구절 반복을 감지하지만 Windows 휴리스틱이 더 보수적 | 중간 | cut analysis tests |
| false-start 감지 | `auto_cut.py` | `analysis/cuts.py` | 예 | 검토용 구현 | prefix restart와 유사 구절 후보를 만들지만 자동 삭제보다는 review 중심 | 중간 | 후보 JSON 확인, cut analysis tests |
| 어/음 필러 감지 | `auto_cut.py`, `config.py` | `analysis/cuts.py` | 예 | 검토용 구현 | 텍스트 기반 후보 중심 | 중간 | 후보 JSON 확인 |
| 음향 기반 필러 감지 | `acoustic_filler.py` | `analysis/acoustic.py`, `pipeline.analyze_cuts` | 예 | 검토용 구현 | 원본 aggressive 삭제와 달리 review signal 중심 | 중간 | audio feature unit test |
| 문장 끝 음절 보호 | `auto_cut.word_snap()` | `timeline/protection.py`, `pipeline.export` | 예 | 부분 구현 | silence 기반 자동 삭제 경계 보호 중심 | 중간 | timeline protection tests |
| 숨소리 감지 및 축소 | `breath_reduce.py` | `audio/breath.py`, `ffmpeg_tools.make_clean_wav` | 예 | 검토용 구현 | 원본과 동일한 품질 보장은 아님. source는 수정하지 않고 clean WAV만 감쇠 | 중간 | audio feature tests, clean WAV smoke |
| 노이즈 플로어 측정 | `auto_cut.measure_noise_floor()` | `audio/features.py` | 예 | 완전 구현 | STT WAV 기준 측정 | 쉬움 | audio feature tests |
| 노이즈 제거 | `auto_cut.py` | `audio/presets.py`, `ffmpeg_tools.py` | 예 | 부분 구현 | FFmpeg `afftdn` clean WAV 중심 | 쉬움 | FFmpeg filter smoke |
| 하이패스 필터 | `silence_cut.py` | `audio/presets.py` | 예 | 완전 구현 | clean WAV filter chain | 쉬움 | filter chain test |
| 컴프레서 | `silence_cut.py` | `audio/presets.py` | 예 | 완전 구현 | clean WAV filter chain | 쉬움 | filter chain test |
| LUFS 정규화 | `silence_cut.py` | `audio/presets.py`, `pipeline.export`, `video/analyze.py` | 예 | 부분 구현 | clean WAV loudnorm filter와 전후 loudnorm sidecar를 제공하지만 원본 세팅과 완전 동일하지는 않음 | 쉬움 | filter chain test, clean WAV smoke |
| 치찰음 감소 | `auto_cut.py` | `audio/presets.py` | 예 | 부분 구현 | FFmpeg deesser 사용. 원본 세팅과 완전 동일하지 않음 | 쉬움 | filter chain test |
| natural/podcast 프리셋 | `auto_cut.py` | `audio/presets.py`, `cli.py` | 예 | 부분 구현 | Windows filter preset으로 재구현 | 중간 | parser/filter tests |
| SRT 생성 | `make_subtitles.py`, `subtitle_polish.py` | `subtitles/srt.py`, `pipeline.export` | 예 | 완전 구현 | 컷 타임라인 remap 반영 | 쉬움 | subtitle tests, mocked E2E |
| VTT 생성 | `subtitle_polish.py` | `subtitles/vtt.py`, `pipeline.export` | 예 | 완전 구현 | 기본 writer 구현 | 쉬움 | subtitle export tests |
| ASS 생성 | `subtitle_polish.py` | `subtitles/ass.py`, `pipeline.export` | 예 | 완전 구현 | 기본 ASS writer 구현 | 쉬움 | subtitle export tests |
| 강조 ASS | `emphasis_subs.py` | `subtitles/ass.py`, `pipeline.export` | 예 | 부분 구현 | filler 강조 중심. 원본 효과와 완전 동일하지 않음 | 중간 | subtitle export tests |
| 자막 줄 길이 제한 | `make_subtitles.py` | `subtitles/srt.py` | 예 | 부분 구현 | 단순 max chars/gap 중심 | 중간 | subtitle tests |
| 자막 빈 구간 보정 | `subtitle_polish.py` | `subtitles/srt.py` | 예 | 부분 구현 | small gap 보정만 지원 | 쉬움 | subtitle tests |
| FCP7 XML 생성 | `silence_cut.py` | `premiere/fcp7.py`, `pipeline.export` | 예 | 완전 구현 | XML 파싱 테스트 포함 | 중간 | FCP7 XML tests |
| Premiere media path URI | `silence_cut.py` | `paths.windows_file_uri`, `premiere/fcp7.py` | 예 | 완전 구현 | `Path.as_uri()` 기반. UNC는 URI 생성, Premiere import는 환경별 수동 확인 | 중간 | URI/FCP7 tests |
| keep range 생성 | `silence_cut.py` | `timeline/mapper.py`, `pipeline.export` | 예 | 완전 구현 | deletion -> keep mapping | 쉬움 | mapper tests |
| 버린 컷 검토 데이터 | `auto_cut.complement()` | `cut_candidates.json`, `keep_ranges.json`, `cut_review.json`, `rejected.xml`, report | 예 | 완전 구현 | 삭제 구간 JSON과 버린 컷만 이어 붙인 FCP7 XML을 제공 | 중간 | JSON/report/XML parse tests |
| HTML 리포트 | `html_report.py` | `reports/html.py` | 예 | 부분 구현 | 원본 리포트보다 간결하지만 삭제 구간과 촘촘한 컷 구간을 표시 | 쉬움 | report tests |
| transcript export | `transcript_export.py` | `exports/transcript.py`, `pipeline.export` | 예 | 완전 구현 | MD/TXT/CSV 생성 | 쉬움 | subtitle/export tests |
| 편집 전후 diff | `edit_diff.py` | `exports/edit_diff.py`, `pipeline.export` | 예 | 부분 구현 | 원본과 diff 관점이 다름 | 중간 | export smoke |
| 영상 분석 | `analyze_video.py` | `video/analyze.py`, `cli analyze-video` | 예 | 부분 구현 | FFmpeg/ffprobe heuristic | 중간 | CLI smoke |
| 자동 프리셋 추천 | `analyze_video.py` | `video/analyze.py`, `cli recommend-preset` | 예 | 부분 구현 | rule-based recommendation | 중간 | CLI smoke |
| 폴더 일괄 처리 | `batch.sh` | `batch.ps1` | 예 | 완전 구현 | 실패 파일을 모으고 계속 진행 | 쉬움 | PowerShell dry-run |
| 쇼츠 생성 | `make_shorts.py`, `shorts_xml.py` | `shorts/generator.py`, `cli shorts` | 예 | 검토용 구현 | XML-first. MP4 렌더는 선택 | 큼 | shorts tests |
| 세로 영상 처리 | `make_shorts.py` | `shorts/generator.py` | 예 | 검토용 구현 | 9:16 XML/optional MP4 | 큼 | shorts tests |
| 2카메라 동기화 | `sync_2cam.py` | `multicam/sync.py`, `cli sync-2cam` | 예 | 부분 구현 | numpy envelope correlation | 큼 | sync smoke |
| 멀티캠 XML | `mcam_xml.py` | `multicam/xml.py`, `cli multicam-xml` | 예 | 검토용 구현 | explicit offset/multi-track XML | 큼 | multicam tests |
| 자동 카메라 전환 | 원본 별도 로직 일부 | `multicam/switching.py`, `cli auto-multicam-xml` | 예 | 검토용 구현 | keep range를 switch interval로 나누는 보수적 round-robin 휴리스틱 | 큼 | multicam switching tests, XML parse smoke |
| Premiere 자동 렌더링 | 없음/수동 | `premiere/automation.py`, `cli premiere-script`, `cli premiere-launch` | 예 | 검토용 구현 | JSX 생성/실행기 제공. 실제 Premiere/Media Encoder 성공 여부는 GUI 환경 수동 검증 필요 | 큼 | JSX generation tests |
| Claude agent/skill 연동 | `.claude/*` | `claude_assets.py`, `cli doctor`, manifest | 예 | 부분 구현 | 자산 발견/기록은 되지만 모든 agent 문구가 Windows 명령과 완전 동기화되지는 않음 | 쉬움 | claude asset tests |

## 이번 검수에서 수정한 핵심 문제

- `--limit-seconds`가 STT WAV에만 적용되던 의미를 전체 파이프라인 제한으로 수정했다.
- STT 전용 제한은 `--stt-limit-seconds`와 기존 호환 alias `--transcribe-seconds`로 분리했다.
- `--smoke-seconds`를 전체 파이프라인 스모크 제한 alias로 추가했다.
- clean WAV, silence analysis, candidate analysis, XML, SRT/VTT/ASS, report, keep range가 같은 제한 시간을 사용하게 했다.
- FCP7 XML media URI를 수동 조립에서 `Path.as_uri()` 기반으로 바꿨다.
- 같은 stem의 기존 manifest가 다른 입력 파일을 가리키면 output name에 짧은 hash를 붙여 덮어쓰기를 피한다.
- `--output-dir`, `--output-name`, `--overwrite`를 추가했다.
- 일반 CLI 오류는 traceback 없이 간단히 출력하고, `--debug`에서만 traceback을 표시한다.
- install/run/batch PowerShell wrapper의 입력/venv 확인과 batch 성공/실패 목록을 보강했다.
- `auto-multicam-xml`로 자동 카메라 전환용 단일 러프컷 XML과 switch plan JSON을 생성한다.
- `premiere-script`와 `premiere-launch`로 Premiere XML/SRT import 및 선택적 MP4 export JSX를 생성하고 Premiere 실행 진입점을 제공한다.
- transcript cache를 추가했다. 입력 파일, 크기/mtime, 모델, 언어, chunk, STT 제한 시간이 모두 같을 때만 재사용하며 `--no-transcript-cache`로 강제 재실행할 수 있다.
- 반복 구절 감지와 prefix false-start 감지를 추가했다.
- `*_cut_review.json`과 `*_rejected.xml`을 추가해 버린 컷 검토 데이터를 Premiere XML로도 확인할 수 있게 했다.
- clean WAV 생성 시 `*_audio_loudness.json`에 원본/clean WAV loudnorm 측정값을 기록한다.

## 권장 구현 순서 상태

| 단계 | 범위 | 현재 상태 |
|---|---|---|
| 1단계 | 핵심 파이프라인, 경로, STT, 컷 후보, XML, SRT, report, clean WAV | 완료, 추가 안정화 완료 |
| 2단계 | VTT, ASS, 강조 자막, transcript export, edit diff | 완료 |
| 3단계 | 음향 기반 필러, 끝음 보호, 숨소리 축소, 노이즈/치찰음/오디오 프리셋 | 부분/검토용 구현 완료 |
| 4단계 | 영상 분석, 자동 프리셋 추천, 쇼츠, 세로 영상, 2카메라 동기화, multicam XML, 자동 카메라 전환, Premiere JSX 자동화 | 부분/검토용 구현 완료 |

## 위험 요소

- Premiere Pro의 FCP7 XML import 결과는 Premiere 버전과 media path 환경에 따라 달라질 수 있다.
- UNC URI는 생성되지만, Premiere에서 실패하면 네트워크 드라이브 문자 매핑이 필요하다.
- Whisper large-v3는 VRAM 사용량이 크다. 이 포트는 모델을 자동 하향하지 않는다.
- acoustic filler, breath, multicam, shorts, 자동 카메라 전환은 검토용/보조 산출물이며 원본의 모든 자동화 품질과 동일하다고 표시하지 않는다.
- Premiere 자동 렌더링은 JSX 생성/실행기까지 지원하지만, 실제 Adobe 앱 내부 렌더 결과는 수동 검증해야 한다.

## 테스트 방법

자동 테스트:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

검증된 테스트 범위:

- Windows drive URI
- 한글/공백/특수문자 URI
- UNC URI
- FCP7 XML 파싱과 media URI 확인
- 같은 파일명 output collision
- `--limit-seconds` 전체 파이프라인 전달
- CLI 오류 메시지 traceback 억제
- mocked STT E2E: FFmpeg 테스트 MP4 -> STT mock -> 컷 분석 -> XML/SRT/manifest 생성
- transcript cache reuse
- rejected XML/review JSON export
- repeated phrase and prefix false-start detection
- VTT/ASS export
- timeline protection
- shorts/multicam helper
- auto multicam switching XML
- Premiere automation JSX generation

수동 검증 필요:

- Premiere Pro에서 `*_cut.xml` import
- Premiere Pro에서 SRT/ASS/VTT 자막 import
- Premiere Pro에서 UNC media path가 정상 relink/import 되는지
- Premiere Pro에서 `premiere-script`가 생성한 JSX import/export가 실제로 실행되는지
- 자동 카메라 전환 XML의 컷 선택이 의도한 편집 감각과 맞는지
- 실제 긴 영상의 컷 품질
- 실제 NVIDIA GPU에서 full Whisper STT 성능과 VRAM 여유
