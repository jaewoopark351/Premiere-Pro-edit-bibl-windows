from __future__ import annotations

from pathlib import Path

from .base import TranscriptResult
from .validation import validate_segments, validate_words
from ..timeline.models import TranscriptSegment, TranscriptWord


class SttRuntimeError(RuntimeError):
    pass


class TransformersWhisperBackend:
    def __init__(self, model: str = "openai/whisper-large-v3") -> None:
        self.model = model

    def transcribe(self, audio_path: Path, language: str = "ko", allow_cpu_fallback: bool = False) -> TranscriptResult:
        try:
            import torch
            from transformers import pipeline
        except Exception as exc:
            raise SttRuntimeError(f"STT dependencies are not installed: {exc}") from exc

        cuda_available = bool(torch.cuda.is_available())
        warnings: list[str] = []
        if cuda_available:
            device = "cuda:0"
            torch_dtype = torch.float16
            pipeline_device = 0
        else:
            warning = "CUDA is not available for Transformers Whisper."
            if not allow_cpu_fallback:
                raise SttRuntimeError(warning + " CPU fallback is disabled.")
            warnings.append(warning + " CPU fallback is enabled by config.")
            device = "cpu"
            torch_dtype = torch.float32
            pipeline_device = -1

        asr = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            dtype=torch_dtype,
            device=pipeline_device,
        )
        result = asr(
            str(audio_path),
            return_timestamps="word",
            chunk_length_s=30,
            batch_size=8,
            generate_kwargs={"language": language, "task": "transcribe"},
        )

        words: list[TranscriptWord] = []
        chunks = result.get("chunks") or []
        for chunk in chunks:
            ts = chunk.get("timestamp") or (None, None)
            start, end = ts
            text = (chunk.get("text") or "").strip()
            if start is None or end is None:
                words.append(TranscriptWord(start=0.0, end=0.0, text=text))
            else:
                words.append(TranscriptWord(start=float(start), end=float(end), text=text))

        text = (result.get("text") or "").strip()
        if words:
            segments = [TranscriptSegment(start=words[0].start, end=words[-1].end, text=text, words=words)]
        else:
            segments = []
        validation = validate_words(words) + validate_segments(segments)
        return TranscriptResult(
            source_audio=str(audio_path),
            backend="transformers-whisper",
            model=self.model,
            language=language,
            device=device,
            text=text,
            segments=segments,
            words=words,
            warnings=warnings,
            validation_issues=validation,
        )
