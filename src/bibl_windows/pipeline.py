from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .analysis.cuts import (
    dedupe_candidates,
    false_start_candidates,
    repeated_speech_candidates,
    short_meaningless_candidates,
    silence_candidates,
)
from .analysis.acoustic import acoustic_filler_candidates
from .artifacts import ArtifactManifest
from .audio.breath import detect_breath_ranges
from .audio.features import AudioFeatureSummary, measure_noise_floor
from .ffmpeg_tools import detect_silence, extract_audio_for_stt, make_clean_wav
from .exports.edit_diff import summarize_edit_diff, write_edit_diff
from .exports.transcript import write_transcript_csv, write_transcript_markdown, write_transcript_text
from .io_json import read_json, write_json
from .media_probe import MediaInfo, probe_media
from .paths import media_stem
from .premiere.fcp7 import build_fcp7_xml
from .reports.html import write_report
from .runtime import RuntimeContext, RuntimeErrorWithHint
from .stt.base import TranscriptResult
from .stt.transformers_whisper import SttRuntimeError, TransformersWhisperBackend
from .subtitles.ass import write_ass
from .subtitles.srt import group_words, polish_cues, write_srt
from .subtitles.vtt import write_vtt
from .timeline.mapper import TimelineMapper
from .timeline.models import CutCandidate, TimeRange, TranscriptWord
from .timeline.protection import protected_candidate_delete_ranges


@dataclass(frozen=True)
class PipelineOptions:
    input_path: Path
    preset_name: str = "standard"
    model: str = "openai/whisper-large-v3"
    language: str = "ko"
    stt_batch_size: int = 1
    stt_chunk_seconds: float = 25.0
    limit_seconds: float | None = None
    allow_cpu_fallback: bool = False
    clean_wav: bool = False
    audio_preset: str = "standard"
    extra_exports: bool = True
    advanced_audio_analysis: bool = True
    command: list[str] | None = None


@dataclass(frozen=True)
class PipelineArtifacts:
    transcript_json: Path | None = None
    stt_audio: Path | None = None
    cut_candidates_json: Path | None = None
    xml: Path | None = None
    srt: Path | None = None
    vtt: Path | None = None
    ass: Path | None = None
    emphasis_ass: Path | None = None
    report: Path | None = None
    clean_wav: Path | None = None
    keep_ranges_json: Path | None = None
    breath_ranges_json: Path | None = None
    transcript_md: Path | None = None
    transcript_txt: Path | None = None
    transcript_csv: Path | None = None
    edit_diff_json: Path | None = None
    edit_diff_md: Path | None = None
    manifest_json: Path | None = None


class WindowsEditPipeline:
    def __init__(self, context: RuntimeContext | None = None) -> None:
        self.context = context or RuntimeContext.discover()

    def probe(self, media_path: Path) -> MediaInfo:
        require_input_file(media_path)
        _ffmpeg, ffprobe = self.context.tools.require_media_tools()
        return probe_media(ffprobe, media_path)

    def transcribe(self, options: PipelineOptions) -> tuple[TranscriptResult, Path, Path]:
        require_input_file(options.input_path)
        ffmpeg, _ffprobe = self.context.tools.require_media_tools()
        stem = media_stem(options.input_path)
        suffix = "_stt_audio.wav" if options.limit_seconds is None else f"_stt_{options.limit_seconds:g}s.wav"
        stt_audio = self.context.paths.output_path(stem + suffix)
        extract_audio_for_stt(ffmpeg, options.input_path, stt_audio, options.limit_seconds)
        try:
            result = TransformersWhisperBackend(options.model).transcribe(
                stt_audio,
                language=options.language,
                allow_cpu_fallback=options.allow_cpu_fallback,
                batch_size=options.stt_batch_size,
                chunk_length_s=options.stt_chunk_seconds,
            )
        except SttRuntimeError as exc:
            fallback_hint = (
                "\nRun `python -m bibl_windows.cli doctor` to inspect CUDA, "
                "or rerun with `--allow-cpu-fallback` for a slow CPU check."
            )
            raise RuntimeErrorWithHint(f"STT failed while transcribing {stt_audio}: {exc}{fallback_hint}") from exc
        transcript_json = self.context.paths.output_path(f"{stem}_transcript.json")
        write_json(transcript_json, result.to_dict())
        return result, transcript_json, stt_audio

    def dry_run(self, options: PipelineOptions) -> dict:
        require_input_file(options.input_path)
        stem = media_stem(options.input_path)
        preset = self.context.load_preset(options.preset_name)
        outdir = self.context.paths.output_dir.resolve()

        def expected_path(name: str) -> str:
            return str((outdir / name).resolve())

        output = {
            "transcript_json": expected_path(f"{stem}_transcript.json"),
            "stt_audio": expected_path(
                stem + ("_stt_audio.wav" if options.limit_seconds is None else f"_stt_{options.limit_seconds:g}s.wav")
            ),
            "cut_candidates_json": expected_path(f"{stem}_cut_candidates.json"),
            "xml": expected_path(f"{stem}_cut.xml"),
            "srt": expected_path(f"{stem}_cut.srt"),
            "vtt": expected_path(f"{stem}_cut.vtt"),
            "ass": expected_path(f"{stem}_cut.ass"),
            "emphasis_ass": expected_path(f"{stem}_cut_emphasis.ass"),
            "report": expected_path(f"{stem}_report.html"),
            "keep_ranges_json": expected_path(f"{stem}_keep_ranges.json"),
            "breath_ranges_json": expected_path(f"{stem}_breath_ranges.json"),
            "transcript_md": expected_path(f"{stem}_transcript.md"),
            "transcript_txt": expected_path(f"{stem}_transcript.txt"),
            "transcript_csv": expected_path(f"{stem}_transcript.csv"),
            "edit_diff_json": expected_path(f"{stem}_edit_diff.json"),
            "edit_diff_md": expected_path(f"{stem}_edit_diff.md"),
            "manifest_json": expected_path(f"{stem}_manifest.json"),
        }
        if options.clean_wav:
            output["clean_wav"] = expected_path(f"{stem}_cut_audio.wav")

        media = None
        media_probe_error = None
        if self.context.tools.ffprobe.path:
            try:
                media = probe_media(self.context.tools.ffprobe.path, options.input_path).to_dict()
            except Exception as exc:
                media_probe_error = str(exc)

        return {
            "dry_run": True,
            "input": str(options.input_path),
            "input_resolved": str(options.input_path.resolve()),
            "preset": options.preset_name,
            "model": options.model,
            "language": options.language,
            "stt_batch_size": options.stt_batch_size,
            "stt_chunk_seconds": options.stt_chunk_seconds,
            "limit_seconds": options.limit_seconds,
            "allow_cpu_fallback": options.allow_cpu_fallback,
            "clean_wav": options.clean_wav,
            "audio_preset": options.audio_preset,
            "extra_exports": options.extra_exports,
            "advanced_audio_analysis": options.advanced_audio_analysis,
            "tools": {
                "ffmpeg": {
                    "available": self.context.tools.ffmpeg.available,
                    "path": str(self.context.tools.ffmpeg.path) if self.context.tools.ffmpeg.path else None,
                },
                "ffprobe": {
                    "available": self.context.tools.ffprobe.available,
                    "path": str(self.context.tools.ffprobe.path) if self.context.tools.ffprobe.path else None,
                },
            },
            "media": media,
            "media_probe_error": media_probe_error,
            "preset_config": preset,
            "expected_outputs": output,
            "will_run_stt": False,
            "will_write_outputs": False,
        }

    def analyze_cuts(
        self,
        media_path: Path,
        preset_name: str,
        transcript_json: Path | None,
        stt_audio_path: Path | None = None,
        advanced_audio_analysis: bool = True,
    ) -> tuple[MediaInfo, list[CutCandidate], Path]:
        require_input_file(media_path)
        ffmpeg, ffprobe = self.context.tools.require_media_tools()
        preset = self.context.load_preset(preset_name)
        media = probe_media(ffprobe, media_path)
        silences = detect_silence(
            ffmpeg,
            media_path,
            float(preset["silence"]["noise_db"]),
            float(preset["silence"]["min_silence"]),
            media.duration,
        )
        cut_cfg = preset["cuts"]
        candidates = silence_candidates(
            silences,
            media.duration,
            float(cut_cfg["long_silence"]),
            float(cut_cfg["start_wait"]),
            float(cut_cfg["end_silence"]),
            float(cut_cfg["pad_before"]),
            float(cut_cfg["pad_after"]),
        )
        audio_analysis: dict = {}
        if transcript_json and transcript_json.exists():
            words = load_transcript_words(transcript_json)
            candidates += repeated_speech_candidates(words, float(cut_cfg["repeat_gap"]), float(cut_cfg["word_pad"]))
            candidates += false_start_candidates(
                words,
                float(cut_cfg["repeat_gap"]),
                float(cut_cfg["word_pad"]),
                float(cut_cfg["false_start_ratio"]),
            )
            candidates += short_meaningless_candidates(
                words,
                float(cut_cfg["short_utterance_max_duration"]),
                float(cut_cfg["word_pad"]),
            )
            if advanced_audio_analysis and stt_audio_path and stt_audio_path.exists():
                noise = measure_noise_floor(stt_audio_path)
                breath_ranges = detect_breath_ranges(stt_audio_path, words, noise, media.duration)
                candidates += acoustic_filler_candidates(stt_audio_path, words, noise, media.duration)
                candidates += [
                    CutCandidate(
                        start=item.start,
                        end=item.end,
                        reason="breath_noise",
                        confidence=0.5,
                        auto_delete=False,
                        requires_review=True,
                        metadata={"source": "audio_features"},
                    )
                    for item in breath_ranges
                ]
                audio_analysis = {
                    "noise_floor": noise.to_dict(),
                    "breath_ranges": [item.__dict__ for item in breath_ranges],
                }
        candidates = dedupe_candidates(candidates)
        out = self.context.paths.output_path(f"{media_stem(media_path)}_cut_candidates.json")
        write_json(
            out,
            {
                "media": media.to_dict(),
                "preset": preset_name,
                "audio_analysis": audio_analysis,
                "candidates": [c.to_dict() for c in candidates],
            },
        )
        return media, candidates, out

    def export(
        self,
        media_path: Path,
        preset_name: str,
        candidates_json: Path,
        transcript_json: Path | None,
        clean_wav_enabled: bool,
        audio_preset: str = "standard",
        stt_audio_path: Path | None = None,
        extra_exports: bool = True,
    ) -> PipelineArtifacts:
        require_input_file(media_path)
        ffmpeg, ffprobe = self.context.tools.require_media_tools()
        stem = media_stem(media_path)
        media = probe_media(ffprobe, media_path)
        candidates = load_candidates(candidates_json)
        words = load_transcript_words(transcript_json) if transcript_json else []
        deletions = protected_candidate_delete_ranges(candidates, words, media.duration, media.video.fps)
        mapper = TimelineMapper(media.duration, media.video.fps, deletions)

        mapped_words = mapper.remap_words(words)
        cues = polish_cues(group_words(mapped_words))
        srt_path = self.context.paths.output_path(f"{stem}_cut.srt")
        write_srt(cues, srt_path)

        vtt_path = ass_path = emphasis_ass_path = None
        transcript_md = transcript_txt = transcript_csv = None
        edit_diff_json = edit_diff_md = None
        if extra_exports:
            vtt_path = self.context.paths.output_path(f"{stem}_cut.vtt")
            ass_path = self.context.paths.output_path(f"{stem}_cut.ass")
            emphasis_ass_path = self.context.paths.output_path(f"{stem}_cut_emphasis.ass")
            write_vtt(cues, vtt_path)
            write_ass(cues, ass_path, title=f"{stem} subtitles")
            write_ass(cues, emphasis_ass_path, title=f"{stem} emphasis subtitles", emphasize=True)
            transcript_md = self.context.paths.output_path(f"{stem}_transcript.md")
            transcript_txt = self.context.paths.output_path(f"{stem}_transcript.txt")
            transcript_csv = self.context.paths.output_path(f"{stem}_transcript.csv")
            write_transcript_markdown(words, transcript_md, stem)
            write_transcript_text(words, transcript_txt)
            write_transcript_csv(words, transcript_csv)
            edit_diff_json = self.context.paths.output_path(f"{stem}_edit_diff.json")
            edit_diff_md = self.context.paths.output_path(f"{stem}_edit_diff.md")
            write_edit_diff(
                summarize_edit_diff(words, deletions, mapper.edited_duration, media.duration),
                edit_diff_json,
                edit_diff_md,
            )

        noise: AudioFeatureSummary | None = None
        breath_ranges: list[TimeRange] = []
        breath_ranges_path = None
        if stt_audio_path and stt_audio_path.exists() and words:
            noise = measure_noise_floor(stt_audio_path)
            breath_ranges = detect_breath_ranges(stt_audio_path, words, noise, media.duration)
            breath_ranges_path = self.context.paths.output_path(f"{stem}_breath_ranges.json")
            write_json(
                breath_ranges_path,
                {
                    "noise_floor": noise.to_dict(),
                    "breath_ranges": [item.__dict__ for item in breath_ranges],
                    "note": "Ranges are attenuated only in generated clean WAV output, never in the source media.",
                },
            )

        clean_wav_path = None
        if clean_wav_enabled:
            clean_wav_path = self.context.paths.output_path(f"{stem}_cut_audio.wav")
            make_clean_wav(
                ffmpeg,
                media_path,
                clean_wav_path,
                media.audio.sample_rate,
                media.audio.channels,
                audio_preset=audio_preset,
                noise_floor_db=noise.noise_floor_db if noise else None,
                breath_ranges=breath_ranges,
            )

        xml_path = self.context.paths.output_path(f"{stem}_cut.xml")
        xml_path.write_text(
            build_fcp7_xml(media, mapper.keeps, f"{stem} [Windows rough cut]", clean_wav_path),
            encoding="utf-8",
            newline="\n",
        )
        report_path = self.context.paths.output_path(f"{stem}_report.html")
        write_report(
            report_path,
            stem,
            candidates,
            {
                "preset": preset_name,
                "duration": media.duration,
                "edited_duration": mapper.edited_duration,
                "removed_duration": max(0.0, media.duration - mapper.edited_duration),
                "deletion_ranges": len(deletions),
                "keep_ranges": len(mapper.keeps),
                "auto_delete_candidates": sum(1 for c in candidates if c.auto_delete and not c.requires_review),
                "review_candidates": sum(1 for c in candidates if c.requires_review),
                "audio_preset": audio_preset,
                "noise_floor_db": None if noise is None else round(noise.noise_floor_db, 2),
                "breath_ranges": len(breath_ranges),
            },
        )
        keep_ranges_path = self.context.paths.output_path(f"{stem}_keep_ranges.json")
        write_json(
            keep_ranges_path,
            {
                "deletions": [d.__dict__ for d in deletions],
                "keeps": [k.__dict__ for k in mapper.keeps],
                "edited_duration": mapper.edited_duration,
                "speech_boundary_protection": True,
            },
        )
        return PipelineArtifacts(
            xml=xml_path,
            srt=srt_path,
            vtt=vtt_path,
            ass=ass_path,
            emphasis_ass=emphasis_ass_path,
            report=report_path,
            clean_wav=clean_wav_path,
            keep_ranges_json=keep_ranges_path,
            breath_ranges_json=breath_ranges_path,
            transcript_md=transcript_md,
            transcript_txt=transcript_txt,
            transcript_csv=transcript_csv,
            edit_diff_json=edit_diff_json,
            edit_diff_md=edit_diff_md,
        )

    def run(self, options: PipelineOptions) -> PipelineArtifacts:
        stem = media_stem(options.input_path)
        manifest = ArtifactManifest(
            media_path=str(options.input_path),
            preset=options.preset_name,
            mode="full" if options.limit_seconds is None else "limited",
            command=options.command or [],
            limit_seconds=options.limit_seconds,
        )
        manifest.metadata["claude"] = self.context.claude.summary()
        result, transcript_json, stt_audio = self.transcribe(options)
        manifest.add("transcript_json", transcript_json)
        manifest.add("stt_audio", stt_audio)
        manifest.metadata["stt"] = {
            "backend": result.backend,
            "model": result.model,
            "device": result.device,
            "words": len(result.words),
            "segments": len(result.segments),
            "validation_issues": result.validation_issues,
            "warnings": result.warnings,
        }
        _media, candidates, candidates_json = self.analyze_cuts(
            options.input_path,
            options.preset_name,
            transcript_json,
            stt_audio,
            options.advanced_audio_analysis,
        )
        manifest.add("cut_candidates_json", candidates_json)
        candidate_payload = read_json(candidates_json)
        manifest.metadata["cut_candidates"] = {"count": len(candidates)}
        manifest.metadata["audio_analysis"] = candidate_payload.get("audio_analysis", {})
        exported = self.export(
            options.input_path,
            options.preset_name,
            candidates_json,
            transcript_json,
            options.clean_wav,
            audio_preset=options.audio_preset,
            stt_audio_path=stt_audio,
            extra_exports=options.extra_exports,
        )
        for key, path in exported.__dict__.items():
            manifest.add(key, path)
        manifest_path = self.context.paths.output_path(f"{stem}_manifest.json")
        manifest.write(manifest_path)
        return PipelineArtifacts(
            transcript_json=transcript_json,
            stt_audio=stt_audio,
            cut_candidates_json=candidates_json,
            xml=exported.xml,
            srt=exported.srt,
            vtt=exported.vtt,
            ass=exported.ass,
            emphasis_ass=exported.emphasis_ass,
            report=exported.report,
            clean_wav=exported.clean_wav,
            keep_ranges_json=exported.keep_ranges_json,
            breath_ranges_json=exported.breath_ranges_json,
            transcript_md=exported.transcript_md,
            transcript_txt=exported.transcript_txt,
            transcript_csv=exported.transcript_csv,
            edit_diff_json=exported.edit_diff_json,
            edit_diff_md=exported.edit_diff_md,
            manifest_json=manifest_path,
        )


def load_transcript_words(path: Path) -> list[TranscriptWord]:
    data = read_json(path)
    words = data.get("words", data if isinstance(data, list) else [])
    return [
        TranscriptWord(
            start=float(w["start"]),
            end=float(w["end"]),
            text=str(w["text"]),
            confidence=w.get("confidence"),
        )
        for w in words
    ]


def load_candidates(path: Path) -> list[CutCandidate]:
    data = read_json(path)
    return [CutCandidate(**candidate) for candidate in data["candidates"]]


def require_input_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeErrorWithHint(
            "Input media file was not found: "
            + str(path)
            + "\nReplace the example path with a real video path. "
            + "For example: C:\\Users\\<name>\\Videos\\recording.mp4"
        )
    if not path.is_file():
        raise RuntimeErrorWithHint(f"Input path is not a file: {path}")
