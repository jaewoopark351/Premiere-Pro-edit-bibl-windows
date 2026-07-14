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

    def transcribe(
        self,
        audio_path: Path,
        language: str = "ko",
        allow_cpu_fallback: bool = False,
        batch_size: int = 1,
        chunk_length_s: float = 25.0,
        initial_prompt: str | None = None,
        condition_on_previous_text: bool = True,
    ) -> TranscriptResult:
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

        try:
            asr = pipeline(
                "automatic-speech-recognition",
                model=self.model,
                dtype=torch_dtype,
                device=pipeline_device,
            )
            generate_kwargs = build_generate_kwargs(
                asr,
                language=language,
                initial_prompt=initial_prompt,
                condition_on_previous_text=condition_on_previous_text,
                warnings=warnings,
            )
            result = asr(
                str(audio_path),
                return_timestamps="word",
                chunk_length_s=max(5.0, float(chunk_length_s)),
                batch_size=max(1, int(batch_size)),
                generate_kwargs=generate_kwargs,
            )
        except Exception as exc:
            if cuda_available:
                try:
                    torch.cuda.empty_cache()
                except Exception:
                    pass
            message = str(exc)
            if "out of memory" in message.lower():
                raise SttRuntimeError(
                    "CUDA ran out of memory during Whisper transcription. "
                    "Close other GPU apps, keep `--stt-batch-size 1`, lower "
                    "`--stt-chunk-seconds`, or select the intended GPU with "
                    "`CUDA_VISIBLE_DEVICES`. This port intentionally keeps "
                    "`openai/whisper-large-v3` as the default model and does "
                    "not automatically downgrade it. "
                    f"Original error: {message}"
                ) from exc
            raise SttRuntimeError(f"Whisper transcription failed: {message}") from exc

        chunks = result.get("chunks") or []
        words = words_from_chunks(chunks, warnings)
        text = (result.get("text") or "").strip()
        if text and chunks and not words:
            raise SttRuntimeError(
                "Whisper returned text but no usable word timestamps. "
                "Refusing to place words at 0 seconds because that corrupts subtitles and cut analysis."
            )
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


def build_generate_kwargs(
    asr,
    language: str,
    initial_prompt: str | None,
    condition_on_previous_text: bool,
    warnings: list[str],
) -> dict:
    kwargs = {
        "language": language,
        "task": "transcribe",
        "condition_on_prev_tokens": bool(condition_on_previous_text),
        # Word-level timestamps keep a cross-attention tensor per generated token.
        # Music/singing chunks can make Whisper hallucinate far more tokens than any
        # real 25-30s speech chunk needs, which blows past 16GB of VRAM. Capping
        # max_new_tokens bounds that worst case without affecting normal speech.
        "max_new_tokens": 256,
    }
    if not initial_prompt:
        return kwargs
    tokenizer = getattr(asr, "tokenizer", None)
    get_prompt_ids = getattr(tokenizer, "get_prompt_ids", None)
    if get_prompt_ids is None:
        warnings.append("Whisper tokenizer does not support prompt_ids; initial prompt was skipped.")
        return kwargs
    try:
        import torch

        prompt_ids = get_prompt_ids(initial_prompt)
        if not isinstance(prompt_ids, torch.Tensor):
            prompt_ids = torch.as_tensor(prompt_ids, dtype=torch.long)
        model_device = getattr(getattr(asr, "model", None), "device", None)
        if model_device is not None:
            prompt_ids = prompt_ids.to(device=model_device)
        kwargs["prompt_ids"] = prompt_ids.to(dtype=torch.long)
    except Exception as exc:
        warnings.append(f"Whisper initial prompt was skipped: {exc}")
    return kwargs


def words_from_chunks(chunks: list[dict], warnings: list[str]) -> list[TranscriptWord]:
    words: list[TranscriptWord] = []
    for chunk in chunks:
        ts = chunk.get("timestamp") or (None, None)
        start, end = ts
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        if start is None or end is None:
            warnings.append(f"Skipped word without timestamp: {text}")
            continue
        start_f = float(start)
        end_f = float(end)
        if end_f <= start_f:
            warnings.append(f"Skipped word with invalid timestamp {start_f}->{end_f}: {text}")
            continue
        words.append(TranscriptWord(start=start_f, end=end_f, text=text))
    return words
