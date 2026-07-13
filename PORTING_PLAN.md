# Porting Plan: Premiere-Pro-edit-bibl Windows NVIDIA Edition

Status: Stage 1 analysis only. No Windows implementation code has been written yet.

Source repository: https://github.com/biblcontentofficial-art/Premiere-Pro-edit-bibl
Local read-only source inspected from: `C:\Vtuber_Souorce_Code\Claude\Premiere-Pro-edit-bibl_window`
Target repository: `C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows`

## Goals

Build a Windows-first, NVIDIA CUDA-first project inspired by the original macOS Apple Silicon tool. This is not a conditional-port of the original tree. The Windows version will use a new package structure, a separate virtual environment, PowerShell entrypoints, `pathlib.Path`, subprocess argument arrays, and output confinement under the project `output` directory.

## Source File And Module Structure

Top-level source files:

- `README.md`: Korean/English product description, macOS Apple Silicon requirements, install and usage instructions.
- `ROADMAP.md`: current feature list and planned improvements.
- `CLAUDE.md`: project context for Claude Code agent workflows.
- `requirements.txt`: `mlx-whisper`, `numpy`; ffmpeg is documented as an external Homebrew dependency.
- `edit.sh`: Bash single-file entrypoint calling `engine/auto_cut.py`.
- `batch.sh`: Bash batch entrypoint over video extensions.
- `config.json.example`: user override example for tuning presets.
- `LICENSE`: MIT license.

Engine modules:

- `engine/auto_cut.py`: current orchestration layer. Runs media probing, silence detection, audio cleanup, STT cache, filler/repeat/NG/breath removal, XML, SRT, optional HTML report.
- `engine/silence_cut.py`: ffmpeg/ffprobe probing, silence detection, loudness measurement, clean WAV generation, FCP7 XML generation.
- `engine/make_subtitles.py`: `mlx_whisper` transcription, source-time to cut-time mapping, Korean subtitle grouping, SRT writing.
- `engine/config.py`: built-in defaults and `보수` / `표준` / `공격` presets.
- `engine/subtitle_polish.py`: SRT cleanup, VTT/ASS output, reading-speed and timing sanitization.
- `engine/html_report.py`: HTML inspection report generator.
- `engine/acoustic_filler.py`: numpy-based acoustic hesitation detection for voiced flat pitch plateaus.
- `engine/breath_reduce.py`: numpy-based breath detection between transcript words.
- `engine/analyze_video.py`: ffmpeg-based video measurement and preset recommendation.
- `engine/transcript_export.py`: `_words.json` to Markdown transcript export.
- `engine/edit_diff.py`: compares original transcript, generated cut XML, and final transcript for calibration.
- `engine/make_shorts.py`: direct ffmpeg generation of vertical MP4 shorts.
- `engine/shorts_xml.py`: editable 9:16 FCP7 XML short sequence generation.
- `engine/shorts_cut.py`: cut-timeline-aware short XML and SRT generation.
- `engine/mcam_xml.py`: multi-camera FCP7 XML generation from a master cut.
- `engine/sync_2cam.py`: audio-envelope cross-correlation sync offset calculation.
- `engine/emphasis_subs.py`: ASS subtitle emphasis coloring.

## macOS-Specific Elements

- Apple Silicon is a documented runtime requirement because `mlx-whisper` depends on Apple's MLX stack.
- `edit.sh` and `batch.sh` assume Bash and POSIX shell behavior.
- README install instructions use `brew install ffmpeg`.
- README uses `chmod +x edit.sh batch.sh`.
- README Premiere tips use macOS shortcuts such as `Cmd+I` and `Cmd+Shift+D`.
- Several modules default to `~/bin/ffmpeg` or `~/bin/ffprobe` before falling back to PATH.
- XML path construction uses `os.path.abspath()` plus `urllib.parse.quote()` and may produce Windows-hostile `file://C%3A/...` or backslash-encoded URLs if reused directly.

## mlx-whisper Dependency Areas

- `requirements.txt` depends directly on `mlx-whisper`.
- `engine/config.py` default `STT_MODEL` is `mlx-community/whisper-large-v3-turbo`.
- `engine/make_subtitles.py` imports `mlx_whisper` inside `transcribe()`.
- `engine/auto_cut.py` imports `transcribe()` from `make_subtitles.py` and therefore depends on `mlx_whisper` for normal full runs.
- `_words.json` cache format is currently a simple list of `[start, end, text]` word triples, not a rich STT result schema.

Windows decision:

- Do not use `mlx-whisper` in Windows code.
- Create an STT backend interface.
- First backend: Hugging Face Transformers Whisper using `openai/whisper-large-v3`.
- Store richer JSON with metadata, segments, words, backend, model, device, CUDA status, and validation issues.

## Homebrew Dependency Areas

- README says `brew install ffmpeg`.
- `requirements.txt` comments say ffmpeg is installed via Homebrew and includes ffprobe.

Windows decision:

- Detect `ffmpeg.exe` and `ffprobe.exe` from PATH or explicit config.
- Do not modify persistent PATH.
- Do not install FFmpeg automatically unless the user explicitly runs install guidance.

## Shell Script Dependency Areas

- `edit.sh` uses Bash argument handling and `python3`.
- `batch.sh` uses Bash arrays, `shopt`, POSIX globbing, and `python3`.

Windows decision:

- Replace with `install.ps1`, `run.ps1`, and `batch.ps1`.
- Python entrypoints should also work via `python -m bibl_windows ...`.
- Avoid PowerShell string command composition for ffmpeg calls. Python must call subprocess with argument arrays.

## POSIX Path Dependency Areas

- `~/bin/ffmpeg` and `~/bin/ffprobe` are used in `silence_cut.py`, `acoustic_filler.py`, `breath_reduce.py`, and `sync_2cam.py`.
- `os.path` string manipulation is used everywhere.
- XML `pathurl` generation is not Windows-specific and needs replacement.
- Output paths are generally computed relative to project root but not enforced through a safety boundary.

Windows decision:

- Use `pathlib.Path` in all new Python code.
- Centralize project-root, input, and output path validation.
- Enforce output writes under `output`.
- Generate Windows media URIs as `file:///C:/...` with URL-encoded path segments.

## Functions And Code Likely To Break On Windows

- `make_subtitles.transcribe()`: imports `mlx_whisper`; not usable on Windows.
- `silence_cut.build_fcp7_xml()`: path URL generation is not Windows-correct.
- `shorts_xml.build_xml()`, `shorts_cut.build_short()`, `mcam_xml.file_def()`: same Windows file URI risk.
- `edit.sh` and `batch.sh`: not native Windows entrypoints.
- `requirements.txt`: installs macOS-only STT backend.
- `probe_media()` fallback parsing may work but should be replaced with ffprobe JSON as the required Windows path.
- `HAS_FFPROBE` detection uses slash checks and POSIX assumptions.
- `subtitle_polish.main()` writes `.srt.bak` beside the input. In the Windows version, backup/output writes must be constrained to the project output tree.
- `backup_outputs()` uses `_backup` under output and is mostly safe, but needs project-boundary checks.
- Any direct `open()` writes should be replaced with path utilities that validate output location.

## Modules Reusable As-Is

No module should be copied as-is into the Windows version because the new project should be Windows-first and needs license provenance on reused code.

Algorithmic ideas reusable with attribution:

- Korean subtitle chunking heuristics from `make_subtitles.py`.
- SRT/VTT/ASS formatting concepts from `subtitle_polish.py`.
- Conservative silence-to-keep-range logic from `silence_cut.py`.
- Repetition and false-start detection logic from `auto_cut.py`.
- HTML report concept and basic category layout from `html_report.py`.
- Multi-camera and shorts XML ideas may be revisited after the core pipeline is verified.

## Modules To Modify And Port Conceptually

- `silence_cut.py`: split into Windows media probing, silence detection, audio cleanup, and FCP7 XML writer modules.
- `make_subtitles.py`: replace STT implementation; keep only mapping and subtitle grouping concepts.
- `auto_cut.py`: replace monolithic orchestration with explicit pipeline stages and JSON artifacts.
- `config.py`: convert to JSON presets under `config/`.
- `html_report.py`: keep concept, rewrite output with escaped structured data.
- `subtitle_polish.py`: keep SRT timing and sanitization ideas, rewrite around timeline models.

## New Modules To Write

Proposed package: `src/bibl_windows/`

- `paths.py`: project root, output path safety, media path normalization, Windows file URI generation.
- `logging_utils.py`: command logging and report evidence helpers.
- `ffmpeg_tools.py`: ffmpeg/ffprobe discovery, version capture, subprocess wrappers.
- `media_probe.py`: ffprobe JSON parsing into typed media metadata.
- `cuda_probe.py`: torch/CUDA/GPU/VRAM diagnostics.
- `stt/base.py`: STT backend protocol and result models.
- `stt/transformers_whisper.py`: Transformers Whisper backend.
- `stt/validation.py`: timestamp validation for empty, duplicate, reversed, and out-of-range words/segments.
- `timeline/models.py`: `TimeRange`, `TranscriptSegment`, `TranscriptWord`, `CutCandidate`, `KeepRange`.
- `timeline/mapper.py`: deletion merge, keep generation, source-to-edit mapping, frame alignment, SRT remapping.
- `analysis/cuts.py`: silence, start wait, end silence, repeated speech, false start, short meaningless utterance candidates.
- `premiere/fcp7.py`: Windows Premiere FCP7 XML writer.
- `subtitles/srt.py`: SRT writer after cut remap.
- `reports/html.py`: HTML inspection report.
- `cli.py`: `doctor`, `probe`, `transcribe`, `analyze-cuts`, `export`, and end-to-end `run` commands.

## Modules To Discard Initially

These are out of initial Windows MVP scope:

- `edit.sh`
- `batch.sh`
- `mlx_whisper`-based STT implementation
- `make_shorts.py` direct MP4 generation
- `shorts_xml.py`
- `shorts_cut.py`
- `mcam_xml.py`
- `sync_2cam.py`
- `edit_diff.py`
- Claude agent definitions and macOS-oriented docs

They can be revisited after the main long-form Premiere XML workflow is verified.

## Original Code Requiring License Notice

The original repository is MIT licensed. Any copied or substantially adapted implementation must retain attribution and MIT notice in source comments or `THIRD_PARTY_NOTICES.md`.

Likely attribution areas:

- Silence-to-keep range and FCP7 XML concepts from `engine/silence_cut.py`.
- Korean subtitle grouping and SRT formatting concepts from `engine/make_subtitles.py`.
- Repetition, false-start, and NG detection concepts from `engine/auto_cut.py`.
- Preset values and Korean filler phrase lists from `engine/config.py`.
- Subtitle polish ideas from `engine/subtitle_polish.py`.
- HTML report concept from `engine/html_report.py`.

## Implementation Order

1. Create this `PORTING_PLAN.md` from read-only source analysis.
2. Create Windows project skeleton, `.venv`, package layout, config files, docs, and safety utilities.
3. Implement ffmpeg/ffprobe discovery and media probing.
4. Implement torch CUDA/GPU diagnostics.
5. Verify Windows minimal environment on the actual machine.
6. Implement STT backend interface and Transformers Whisper backend.
7. Run 10-30 second real transcription test and save JSON.
8. Implement timeline data models and `TimelineMapper`.
9. Add timeline unit tests and pass them.
10. Implement conservative cut candidate analysis.
11. Implement SRT remapping and writer.
12. Implement Windows FCP7 XML writer and XML validation.
13. Implement HTML review report.
14. Create PowerShell entrypoints.
15. Complete notices, setup docs, and porting report.
16. Run final tests and report verified vs unverified items.

## Expected Risks

- PyTorch CUDA support for RTX 5070 Ti may require a specific recent CUDA-enabled torch build.
- `openai/whisper-large-v3` can be large and slow to download; network may be restricted.
- 16GB VRAM is likely usable, but long files may require chunking and careful dtype/device handling.
- Transformers word timestamps may be less stable than segment timestamps depending on generation settings.
- Premiere FCP7 XML import behavior must be verified by the user in Adobe Premiere Pro.
- Windows file URI handling for Korean paths and spaces is error-prone and must be tested with real paths.
- VFR footage and OBS audio stream variations can cause timing drift.
- Aggressive auto-cutting can damage natural speech; ambiguous content cuts should require human review.
- Large WAV and JSON outputs can be disk-heavy.
- Long Korean VTuber/OBS recordings may contain overlapping speech, game audio, music, and TTS that reduce STT accuracy.

## Stage 1 Verification

Commands executed so far:

- `Get-Location`
- `rg --files`
- `git status --short` from the local source snapshot. Result: not a Git repository.
- `Get-Content -Raw -Encoding UTF8` on README, ROADMAP, CLAUDE, requirements, config, and engine modules.
- `rg` searches for module functions and platform-specific dependencies.
- `New-Item -ItemType Directory -Force -Path 'C:\Vtuber_Souorce_Code\Premiere-Pro-edit-bibl-windows'`

Created files:

- `PORTING_PLAN.md`

Not verified yet:

- Windows virtual environment creation.
- ffmpeg.exe / ffprobe.exe discovery.
- torch CUDA availability.
- Actual GPU name and VRAM.
- Real media probing on a Korean-space path sample.
- Real STT transcription.
- Timeline unit tests.
- FCP7 XML import into Premiere Pro.
