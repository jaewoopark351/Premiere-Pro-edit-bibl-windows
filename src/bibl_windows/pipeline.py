from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from .analysis.cuts import (
    apply_preset_policy,
    dedupe_candidates,
    false_start_candidates,
    hesitation_candidates,
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
from .exports.review import summarize_cut_review
from .exports.transcript import write_transcript_csv, write_transcript_markdown, write_transcript_text
from .io_json import read_json, write_json
from .media_probe import MediaInfo, probe_media
from .paths import ensure_inside, media_stem, safe_output_component, short_path_hash
from .premiere.fcp7 import build_fcp7_xml
from .reports.html import write_report
from .runtime import RuntimeContext, RuntimeErrorWithHint
from .stt.base import TranscriptResult, transcript_result_from_dict
from .stt.transformers_whisper import SttRuntimeError, TransformersWhisperBackend
from .subtitles.ass import write_ass
from .subtitles.srt import group_words, polish_cues, write_srt
from .subtitles.vtt import write_vtt
from .timeline.mapper import TimelineMapper
from .timeline.models import CutCandidate, TimeRange, TranscriptWord
from .timeline.protection import protected_candidate_delete_ranges
from .video.analyze import measure_loudness


KOREAN_VERBATIM_PROMPT = (
    "한국어 원문 그대로 받아쓰기. 어, 음, 엄, 아, 그, 저, 좀, 약간, "
    "그러니까, 그니까, 이제, 막 같은 필러와 반복 발화를 삭제하거나 고치지 말고 그대로 전사."
)


@dataclass(frozen=True)
class PipelineOptions:
    input_path: Path
    preset_name: str = "standard"
    model: str = "openai/whisper-large-v3"
    language: str = "ko"
    stt_batch_size: int = 1
    stt_chunk_seconds: float = 25.0
    limit_seconds: float | None = None
    stt_limit_seconds: float | None = None
    allow_cpu_fallback: bool = False
    clean_wav: bool = True
    audio_preset: str = "natural"
    extra_exports: bool = True
    advanced_audio_analysis: bool = True
    output_dir: str | None = None
    output_name: str | None = None
    overwrite: bool = False
    reuse_transcript_cache: bool = True
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
    cut_review_json: Path | None = None
    rejected_xml: Path | None = None
    audio_loudness_json: Path | None = None
    manifest_json: Path | None = None


@dataclass(frozen=True)
class OutputLayout:
    dir_parts: tuple[str, ...]
    stem: str

    def expected_path(self, output_root: Path, filename: str) -> Path:
        return (output_root.joinpath(*self.dir_parts, filename)).resolve()

    def output_path(self, context: RuntimeContext, filename: str) -> Path:
        return context.paths.output_path(*self.dir_parts, filename)


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
        layout = self.output_layout(options)
        transcribe_limit = transcription_limit(options)
        suffix = "_stt_audio.wav" if transcribe_limit is None else f"_stt_{transcribe_limit:g}s.wav"
        stt_audio = layout.output_path(self.context, layout.stem + suffix)
        transcript_json = layout.output_path(self.context, f"{layout.stem}_transcript.json")
        cached = load_transcript_cache(transcript_json, options, transcribe_limit) if options.reuse_transcript_cache else None
        if cached is not None:
            if not stt_audio.exists():
                extract_audio_for_stt(ffmpeg, options.input_path, stt_audio, transcribe_limit)
            cached.source_audio = str(stt_audio)
            cached.warnings.append("Reused matching transcript cache; pass --no-transcript-cache to force STT.")
            return cached, transcript_json, stt_audio
        extract_audio_for_stt(ffmpeg, options.input_path, stt_audio, transcribe_limit)
        try:
            result = TransformersWhisperBackend(options.model).transcribe(
                stt_audio,
                language=options.language,
                allow_cpu_fallback=options.allow_cpu_fallback,
                batch_size=options.stt_batch_size,
                chunk_length_s=options.stt_chunk_seconds,
                initial_prompt=KOREAN_VERBATIM_PROMPT,
                condition_on_previous_text=True,
            )
        except SttRuntimeError as exc:
            fallback_hint = (
                "\nRun `python -m bibl_windows.cli doctor` to inspect CUDA, "
                "or rerun with `--allow-cpu-fallback` for a slow CPU check."
            )
            raise RuntimeErrorWithHint(f"STT failed while transcribing {stt_audio}: {exc}{fallback_hint}") from exc
        payload = result.to_dict()
        payload["metadata"] = transcript_cache_metadata(options, transcribe_limit)
        write_json(transcript_json, payload)
        return result, transcript_json, stt_audio

    def dry_run(self, options: PipelineOptions) -> dict:
        require_input_file(options.input_path)
        layout = self.output_layout(options)
        transcribe_limit = transcription_limit(options)
        preset = self.context.load_preset(options.preset_name)
        outdir = self.context.paths.output_dir.resolve()

        def expected_path(name: str) -> str:
            return str(layout.expected_path(outdir, name))

        output = {
            "transcript_json": expected_path(f"{layout.stem}_transcript.json"),
            "stt_audio": expected_path(
                layout.stem + ("_stt_audio.wav" if transcribe_limit is None else f"_stt_{transcribe_limit:g}s.wav")
            ),
            "cut_candidates_json": expected_path(f"{layout.stem}_cut_candidates.json"),
            "xml": expected_path(f"{layout.stem}_cut.xml"),
            "srt": expected_path(f"{layout.stem}_cut.srt"),
            "vtt": expected_path(f"{layout.stem}_cut.vtt"),
            "ass": expected_path(f"{layout.stem}_cut.ass"),
            "emphasis_ass": expected_path(f"{layout.stem}_cut_emphasis.ass"),
            "report": expected_path(f"{layout.stem}_report.html"),
            "keep_ranges_json": expected_path(f"{layout.stem}_keep_ranges.json"),
            "breath_ranges_json": expected_path(f"{layout.stem}_breath_ranges.json"),
            "transcript_md": expected_path(f"{layout.stem}_transcript.md"),
            "transcript_txt": expected_path(f"{layout.stem}_transcript.txt"),
            "transcript_csv": expected_path(f"{layout.stem}_transcript.csv"),
            "edit_diff_json": expected_path(f"{layout.stem}_edit_diff.json"),
            "edit_diff_md": expected_path(f"{layout.stem}_edit_diff.md"),
            "cut_review_json": expected_path(f"{layout.stem}_cut_review.json"),
            "rejected_xml": expected_path(f"{layout.stem}_rejected.xml"),
            "manifest_json": expected_path(f"{layout.stem}_manifest.json"),
        }
        if options.clean_wav:
            output["clean_wav"] = expected_path(f"{layout.stem}_cut_audio.wav")
            output["audio_loudness_json"] = expected_path(f"{layout.stem}_audio_loudness.json")

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
            "stt_limit_seconds": options.stt_limit_seconds,
            "transcription_limit_seconds": transcribe_limit,
            "allow_cpu_fallback": options.allow_cpu_fallback,
            "clean_wav": options.clean_wav,
            "audio_preset": options.audio_preset,
            "output_dir": "/".join(layout.dir_parts) if layout.dir_parts else None,
            "output_name": layout.stem,
            "overwrite": options.overwrite,
            "reuse_transcript_cache": options.reuse_transcript_cache,
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
        limit_seconds: float | None = None,
        output_dir: str | None = None,
        output_name: str | None = None,
        overwrite: bool = False,
    ) -> tuple[MediaInfo, list[CutCandidate], Path]:
        require_input_file(media_path)
        ffmpeg, ffprobe = self.context.tools.require_media_tools()
        layout = self.output_layout_for(media_path, output_dir, output_name, overwrite)
        preset = self.context.load_preset(preset_name)
        media = probe_media(ffprobe, media_path)
        analysis_duration = bounded_duration(media.duration, limit_seconds)
        silences = detect_silence(
            ffmpeg,
            media_path,
            float(preset["silence"]["noise_db"]),
            float(preset["silence"]["min_silence"]),
            analysis_duration,
            limit_seconds=analysis_duration if limit_seconds is not None else None,
        )
        cut_cfg = preset["cuts"]
        candidates = silence_candidates(
            silences,
            analysis_duration,
            float(cut_cfg["long_silence"]),
            float(cut_cfg["start_wait"]),
            float(cut_cfg["end_silence"]),
            float(cut_cfg["pad_before"]),
            float(cut_cfg["pad_after"]),
        )
        audio_analysis: dict = {}
        if transcript_json and transcript_json.exists():
            words = limit_words(load_transcript_words(transcript_json), analysis_duration)
            policy = preset.get("policy", {})
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
            if policy.get("remove_hesitation"):
                candidates += hesitation_candidates(
                    silences,
                    words,
                    float(cut_cfg.get("hesitation_min", 0.55)),
                    float(cut_cfg.get("hesitation_pad", cut_cfg["word_pad"])),
                )
            if advanced_audio_analysis and stt_audio_path and stt_audio_path.exists():
                noise = measure_noise_floor(stt_audio_path)
                breath_ranges = detect_breath_ranges(stt_audio_path, words, noise, analysis_duration)
                candidates += acoustic_filler_candidates(stt_audio_path, words, noise, analysis_duration)
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
        candidates = dedupe_candidates(apply_preset_policy(candidates, preset_name, preset))
        out = layout.output_path(self.context, f"{layout.stem}_cut_candidates.json")
        write_json(
            out,
            {
                "media": media.to_dict(),
                "preset": preset_name,
                "limit_seconds": limit_seconds,
                "analysis_duration": analysis_duration,
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
        limit_seconds: float | None = None,
        output_dir: str | None = None,
        output_name: str | None = None,
        overwrite: bool = False,
    ) -> PipelineArtifacts:
        require_input_file(media_path)
        ffmpeg, ffprobe = self.context.tools.require_media_tools()
        layout = self.output_layout_for(media_path, output_dir, output_name, overwrite)
        media = probe_media(ffprobe, media_path)
        timeline_duration = bounded_duration(media.duration, limit_seconds)
        candidates = load_candidates(candidates_json)
        words = limit_words(load_transcript_words(transcript_json), timeline_duration) if transcript_json else []
        deletions = protected_candidate_delete_ranges(candidates, words, timeline_duration, media.video.fps)
        mapper = TimelineMapper(timeline_duration, media.video.fps, deletions)

        mapped_words = mapper.remap_words(words)
        cues = polish_cues(group_words(mapped_words))
        srt_path = layout.output_path(self.context, f"{layout.stem}_cut.srt")
        write_srt(cues, srt_path)

        vtt_path = ass_path = emphasis_ass_path = None
        transcript_md = transcript_txt = transcript_csv = None
        edit_diff_json = edit_diff_md = None
        cut_review_json = rejected_xml_path = audio_loudness_json = None
        if extra_exports:
            vtt_path = layout.output_path(self.context, f"{layout.stem}_cut.vtt")
            ass_path = layout.output_path(self.context, f"{layout.stem}_cut.ass")
            emphasis_ass_path = layout.output_path(self.context, f"{layout.stem}_cut_emphasis.ass")
            write_vtt(cues, vtt_path)
            write_ass(cues, ass_path, title=f"{layout.stem} subtitles")
            write_ass(cues, emphasis_ass_path, title=f"{layout.stem} emphasis subtitles", emphasize=True)
            transcript_md = layout.output_path(self.context, f"{layout.stem}_transcript.md")
            transcript_txt = layout.output_path(self.context, f"{layout.stem}_transcript.txt")
            transcript_csv = layout.output_path(self.context, f"{layout.stem}_transcript.csv")
            write_transcript_markdown(words, transcript_md, layout.stem)
            write_transcript_text(words, transcript_txt)
            write_transcript_csv(words, transcript_csv)
            edit_diff_json = layout.output_path(self.context, f"{layout.stem}_edit_diff.json")
            edit_diff_md = layout.output_path(self.context, f"{layout.stem}_edit_diff.md")
            write_edit_diff(
                summarize_edit_diff(words, deletions, mapper.edited_duration, timeline_duration),
                edit_diff_json,
                edit_diff_md,
            )

        noise: AudioFeatureSummary | None = None
        breath_ranges: list[TimeRange] = []
        breath_ranges_path = None
        if stt_audio_path and stt_audio_path.exists() and words:
            noise = measure_noise_floor(stt_audio_path)
            breath_ranges = detect_breath_ranges(stt_audio_path, words, noise, timeline_duration)
            breath_ranges_path = layout.output_path(self.context, f"{layout.stem}_breath_ranges.json")
            write_json(
                breath_ranges_path,
                {
                    "noise_floor": noise.to_dict(),
                    "breath_ranges": [item.__dict__ for item in breath_ranges],
                    "note": "Ranges are attenuated only in generated clean WAV output, never in the source media.",
                },
            )

        clean_wav_path = None
        loudness_before = loudness_after = None
        if clean_wav_enabled:
            clean_wav_path = layout.output_path(self.context, f"{layout.stem}_cut_audio.wav")
            make_clean_wav(
                ffmpeg,
                media_path,
                clean_wav_path,
                media.audio.sample_rate,
                media.audio.channels,
                audio_preset=audio_preset,
                noise_floor_db=noise.noise_floor_db if noise else None,
                breath_ranges=breath_ranges,
                limit_seconds=timeline_duration if limit_seconds is not None else None,
            )
            loudness_before = measure_loudness(ffmpeg, media_path)
            loudness_after = measure_loudness(ffmpeg, clean_wav_path)
            audio_loudness_json = layout.output_path(self.context, f"{layout.stem}_audio_loudness.json")
            write_json(
                audio_loudness_json,
                {
                    "source_media": str(media_path),
                    "clean_wav": str(clean_wav_path),
                    "before": loudness_before,
                    "after": loudness_after,
                    "audio_preset": audio_preset,
                },
            )

        xml_path = layout.output_path(self.context, f"{layout.stem}_cut.xml")
        media_for_xml = replace(media, duration=timeline_duration) if limit_seconds is not None else media
        xml_path.write_text(
            build_fcp7_xml(media_for_xml, mapper.keeps, f"{layout.stem} [Windows rough cut]", clean_wav_path),
            encoding="utf-8",
            newline="\n",
        )
        review_summary = summarize_cut_review(candidates, deletions, mapper.keeps, timeline_duration)
        if extra_exports:
            cut_review_json = layout.output_path(self.context, f"{layout.stem}_cut_review.json")
            write_json(cut_review_json, review_summary)
            if deletions:
                rejected_xml_path = layout.output_path(self.context, f"{layout.stem}_rejected.xml")
                rejected_xml_path.write_text(
                    build_fcp7_xml(media_for_xml, deletions, f"{layout.stem} [Rejected cuts review]", None),
                    encoding="utf-8",
                    newline="\n",
                )
        report_path = layout.output_path(self.context, f"{layout.stem}_report.html")
        write_report(
            report_path,
            layout.stem,
            candidates,
            {
                "preset": preset_name,
                "duration": timeline_duration,
                "source_duration": media.duration,
                "edited_duration": mapper.edited_duration,
                "removed_duration": max(0.0, timeline_duration - mapper.edited_duration),
                "deletion_ranges": len(deletions),
                "keep_ranges": len(mapper.keeps),
                "auto_delete_candidates": sum(1 for c in candidates if c.auto_delete and not c.requires_review),
                "review_candidates": sum(1 for c in candidates if c.requires_review),
                "audio_preset": audio_preset,
                "noise_floor_db": None if noise is None else round(noise.noise_floor_db, 2),
                "breath_ranges": len(breath_ranges),
                "rejected_ranges": review_summary["rejected_ranges"],
                "choppy_sections": review_summary["choppy_sections"],
                "loudness_before": loudness_before,
                "loudness_after": loudness_after,
            },
        )
        keep_ranges_path = layout.output_path(self.context, f"{layout.stem}_keep_ranges.json")
        write_json(
            keep_ranges_path,
            {
                "deletions": [d.__dict__ for d in deletions],
                "keeps": [k.__dict__ for k in mapper.keeps],
                "edited_duration": mapper.edited_duration,
                "source_duration": media.duration,
                "timeline_duration": timeline_duration,
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
            cut_review_json=cut_review_json,
            rejected_xml=rejected_xml_path,
            audio_loudness_json=audio_loudness_json,
        )

    def run(self, options: PipelineOptions) -> PipelineArtifacts:
        layout = self.output_layout(options)
        manifest = ArtifactManifest(
            media_path=str(options.input_path),
            preset=options.preset_name,
            mode="full" if options.limit_seconds is None else "limited",
            command=options.command or [],
            limit_seconds=options.limit_seconds,
        )
        manifest.metadata["claude"] = self.context.claude.summary()
        manifest.metadata["output"] = {
            "dir": "/".join(layout.dir_parts) if layout.dir_parts else None,
            "name": layout.stem,
            "overwrite": options.overwrite,
            "reuse_transcript_cache": options.reuse_transcript_cache,
            "stt_limit_seconds": options.stt_limit_seconds,
            "transcription_limit_seconds": transcription_limit(options),
        }
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
            limit_seconds=options.limit_seconds,
            output_dir=options.output_dir,
            output_name=options.output_name,
            overwrite=options.overwrite,
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
            limit_seconds=options.limit_seconds,
            output_dir=options.output_dir,
            output_name=options.output_name,
            overwrite=options.overwrite,
        )
        for key, path in exported.__dict__.items():
            manifest.add(key, path)
        manifest_path = layout.output_path(self.context, f"{layout.stem}_manifest.json")
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
            cut_review_json=exported.cut_review_json,
            rejected_xml=exported.rejected_xml,
            audio_loudness_json=exported.audio_loudness_json,
            manifest_json=manifest_path,
        )

    def output_layout(self, options: PipelineOptions) -> OutputLayout:
        return self.output_layout_for(options.input_path, options.output_dir, options.output_name, options.overwrite)

    def output_layout_for(
        self,
        input_path: Path,
        output_dir: str | None = None,
        output_name: str | None = None,
        overwrite: bool = False,
    ) -> OutputLayout:
        dir_parts = output_dir_parts(output_dir)
        outdir = self.context.paths.output_dir.joinpath(*dir_parts).resolve()
        ensure_inside(outdir, self.context.paths.output_dir.resolve())
        stem = safe_output_component(output_name or media_stem(input_path))
        if output_name is None and not overwrite:
            manifest_path = outdir / f"{stem}_manifest.json"
            if manifest_path.exists():
                try:
                    existing = read_json(manifest_path)
                except Exception as exc:
                    raise RuntimeErrorWithHint(
                        f"Existing manifest is not valid JSON: {manifest_path}\n"
                        "Rerun with --overwrite, --output-name, or --output-dir to choose a new target."
                    ) from exc
                existing_media = existing.get("media_path") if isinstance(existing, dict) else None
                if existing_media and not same_media_path(Path(existing_media), input_path):
                    stem = f"{stem}_{short_path_hash(input_path)}"
        return OutputLayout(dir_parts=dir_parts, stem=stem)


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


def output_dir_parts(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    raw = Path(value)
    if raw.is_absolute():
        raise RuntimeErrorWithHint("Output directory must be relative to the project output directory.")
    parts: list[str] = []
    for part in raw.parts:
        if part in ("", "."):
            continue
        if part == "..":
            raise RuntimeErrorWithHint("Output directory cannot contain '..'.")
        parts.append(safe_output_component(part))
    return tuple(parts)


def same_media_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return str(left).casefold() == str(right).casefold()


def bounded_duration(media_duration: float, limit_seconds: float | None) -> float:
    if limit_seconds is None:
        return media_duration
    if limit_seconds <= 0:
        raise RuntimeErrorWithHint("--limit-seconds and --smoke-seconds must be greater than 0.")
    return min(media_duration, limit_seconds)


def transcription_limit(options: PipelineOptions) -> float | None:
    limit = options.stt_limit_seconds if options.stt_limit_seconds is not None else options.limit_seconds
    if limit is not None and limit <= 0:
        raise RuntimeErrorWithHint("--stt-limit-seconds must be greater than 0.")
    return limit


def transcript_cache_metadata(options: PipelineOptions, transcribe_limit: float | None) -> dict:
    stat = options.input_path.stat()
    return {
        "input_path": str(options.input_path.resolve()),
        "input_size": stat.st_size,
        "input_mtime_ns": stat.st_mtime_ns,
        "model": options.model,
        "language": options.language,
        "stt_chunk_seconds": options.stt_chunk_seconds,
        "initial_prompt": KOREAN_VERBATIM_PROMPT,
        "condition_on_previous_text": True,
        "transcription_limit_seconds": transcribe_limit,
    }


def load_transcript_cache(
    path: Path,
    options: PipelineOptions,
    transcribe_limit: float | None,
) -> TranscriptResult | None:
    if not path.exists():
        return None
    data = read_json(path)
    if not isinstance(data, dict):
        return None
    if data.get("metadata") != transcript_cache_metadata(options, transcribe_limit):
        return None
    try:
        return transcript_result_from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeErrorWithHint(
            f"Transcript cache is invalid: {path}\n"
            "Delete that transcript JSON or rerun with --no-transcript-cache."
        ) from exc


def limit_words(words: list[TranscriptWord], duration: float) -> list[TranscriptWord]:
    limited: list[TranscriptWord] = []
    for word in words:
        if word.start >= duration:
            continue
        limited.append(replace(word, end=min(word.end, duration)))
    return limited


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
