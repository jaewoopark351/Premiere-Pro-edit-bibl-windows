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
from .artifacts import ArtifactManifest
from .ffmpeg_tools import detect_silence, extract_audio_for_stt, make_clean_wav
from .io_json import read_json, write_json
from .media_probe import MediaInfo, probe_media
from .paths import media_stem
from .premiere.fcp7 import build_fcp7_xml
from .reports.html import write_report
from .runtime import RuntimeContext, RuntimeErrorWithHint
from .stt.base import TranscriptResult
from .stt.transformers_whisper import TransformersWhisperBackend
from .subtitles.srt import group_words, write_srt
from .timeline.mapper import TimelineMapper, candidate_delete_ranges
from .timeline.models import CutCandidate, TranscriptWord


@dataclass(frozen=True)
class PipelineOptions:
    input_path: Path
    preset_name: str = "standard"
    model: str = "openai/whisper-large-v3"
    language: str = "ko"
    limit_seconds: float | None = None
    allow_cpu_fallback: bool = False
    clean_wav: bool = False
    command: list[str] | None = None


@dataclass(frozen=True)
class PipelineArtifacts:
    transcript_json: Path | None = None
    stt_audio: Path | None = None
    cut_candidates_json: Path | None = None
    xml: Path | None = None
    srt: Path | None = None
    report: Path | None = None
    clean_wav: Path | None = None
    keep_ranges_json: Path | None = None
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
        result = TransformersWhisperBackend(options.model).transcribe(
            stt_audio,
            language=options.language,
            allow_cpu_fallback=options.allow_cpu_fallback,
        )
        transcript_json = self.context.paths.output_path(f"{stem}_transcript.json")
        write_json(transcript_json, result.to_dict())
        return result, transcript_json, stt_audio

    def analyze_cuts(self, media_path: Path, preset_name: str, transcript_json: Path | None) -> tuple[MediaInfo, list[CutCandidate], Path]:
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
        candidates = dedupe_candidates(candidates)
        out = self.context.paths.output_path(f"{media_stem(media_path)}_cut_candidates.json")
        write_json(out, {"media": media.to_dict(), "preset": preset_name, "candidates": [c.to_dict() for c in candidates]})
        return media, candidates, out

    def export(
        self,
        media_path: Path,
        preset_name: str,
        candidates_json: Path,
        transcript_json: Path | None,
        clean_wav_enabled: bool,
    ) -> PipelineArtifacts:
        require_input_file(media_path)
        ffmpeg, ffprobe = self.context.tools.require_media_tools()
        stem = media_stem(media_path)
        media = probe_media(ffprobe, media_path)
        candidates = load_candidates(candidates_json)
        deletions = candidate_delete_ranges(candidates, media.duration, media.video.fps)
        mapper = TimelineMapper(media.duration, media.video.fps, deletions)

        words = load_transcript_words(transcript_json) if transcript_json else []
        mapped_words = mapper.remap_words(words)
        srt_path = self.context.paths.output_path(f"{stem}_cut.srt")
        write_srt(group_words(mapped_words), srt_path)

        clean_wav_path = None
        if clean_wav_enabled:
            clean_wav_path = self.context.paths.output_path(f"{stem}_cut_audio.wav")
            make_clean_wav(ffmpeg, media_path, clean_wav_path, media.audio.sample_rate, media.audio.channels)

        xml_path = self.context.paths.output_path(f"{stem}_cut.xml")
        xml_path.write_text(
            build_fcp7_xml(media, mapper.keeps, f"{stem} [Windows rough cut]", clean_wav_path),
            encoding="utf-8",
            newline="\n",
        )
        report_path = self.context.paths.output_path(f"{stem}_report.html")
        write_report(report_path, stem, candidates, {"preset": preset_name, "duration": media.duration})
        keep_ranges_path = self.context.paths.output_path(f"{stem}_keep_ranges.json")
        write_json(
            keep_ranges_path,
            {
                "deletions": [d.__dict__ for d in deletions],
                "keeps": [k.__dict__ for k in mapper.keeps],
                "edited_duration": mapper.edited_duration,
            },
        )
        return PipelineArtifacts(
            xml=xml_path,
            srt=srt_path,
            report=report_path,
            clean_wav=clean_wav_path,
            keep_ranges_json=keep_ranges_path,
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
        _media, candidates, candidates_json = self.analyze_cuts(options.input_path, options.preset_name, transcript_json)
        manifest.add("cut_candidates_json", candidates_json)
        manifest.metadata["cut_candidates"] = {"count": len(candidates)}
        exported = self.export(options.input_path, options.preset_name, candidates_json, transcript_json, options.clean_wav)
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
            report=exported.report,
            clean_wav=exported.clean_wav,
            keep_ranges_json=exported.keep_ranges_json,
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
