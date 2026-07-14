from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import wave

from .base import TranscriptResult
from .validation import validate_segments, validate_words
from ..timeline.models import TranscriptSegment, TranscriptWord


MAX_NEW_TOKENS = 256
RETRY_CHUNK_SECONDS = 12.5
EARLY_END_GRACE_SECONDS = 3.0
# HF's chunked long-form generate() does not release the per-chunk
# cross-attention tensors it builds for word timestamps until the whole
# asr() call returns: GPU memory grows with the number of internal chunks
# processed inside a single call. A 240s segment (~14 chunks) still OOM'd on
# a real heavy-hallucination recording even as the very first, freshly
# loaded call, so segments are clamped to at most one Whisper chunk
# (`initial_chunk_seconds`) — that guarantees no within-call accumulation
# across multiple chunks, regardless of how bad a given recording's
# hallucination behavior is. This value is only a fallback for callers that
# do not pass their own chunk length.
SEGMENT_SECONDS = 240.0


class SttRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class TruncationSuspicion:
    suspected: bool
    reason: str | None = None
    retry_start: float | None = None
    retry_end: float | None = None


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
            initial_chunk_seconds = max(5.0, float(chunk_length_s))
            result, truncation_diagnostics = transcribe_long_form(
                asr,
                audio_path,
                initial_chunk_seconds=initial_chunk_seconds,
                retry_chunk_seconds=RETRY_CHUNK_SECONDS,
                batch_size=max(1, int(batch_size)),
                generate_kwargs=generate_kwargs,
                warnings=warnings,
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
            diagnostics={"truncation": truncation_diagnostics},
        )


def run_asr(asr, audio_path: Path, chunk_length_s: float, batch_size: int, generate_kwargs: dict) -> dict:
    return asr(
        str(audio_path),
        return_timestamps="word",
        chunk_length_s=chunk_length_s,
        batch_size=batch_size,
        generate_kwargs=generate_kwargs,
    )


def _free_cuda_cache() -> None:
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _run_asr_with_retry(
    asr,
    audio_path: Path,
    initial_chunk_seconds: float,
    retry_chunk_seconds: float,
    batch_size: int,
    generate_kwargs: dict,
    warnings: list[str],
) -> tuple[dict, dict]:
    result = run_asr(
        asr,
        audio_path,
        chunk_length_s=initial_chunk_seconds,
        batch_size=batch_size,
        generate_kwargs=generate_kwargs,
    )
    return retry_if_truncated(
        asr,
        audio_path,
        result,
        initial_chunk_seconds=initial_chunk_seconds,
        retry_chunk_seconds=retry_chunk_seconds,
        batch_size=batch_size,
        generate_kwargs=generate_kwargs,
        warnings=warnings,
    )


def transcribe_long_form(
    asr,
    audio_path: Path,
    initial_chunk_seconds: float,
    retry_chunk_seconds: float,
    batch_size: int,
    generate_kwargs: dict,
    warnings: list[str],
    segment_seconds: float = SEGMENT_SECONDS,
) -> tuple[dict, dict]:
    """Transcribe audio in independent segments to bound peak GPU memory.

    Each segment gets its own asr() call, so tensors from earlier segments are
    free to be garbage-collected before the next segment starts, instead of
    accumulating across the whole recording in one long generate() call.
    Segments are clamped to at most one Whisper chunk so a single call can
    never internally process more than one chunk, however bad a recording's
    hallucination behavior is.
    """
    segment_seconds = min(segment_seconds, initial_chunk_seconds)
    audio_duration = wav_duration_seconds(audio_path)
    if not audio_duration or audio_duration <= segment_seconds:
        result, truncation = _run_asr_with_retry(
            asr,
            audio_path,
            initial_chunk_seconds=initial_chunk_seconds,
            retry_chunk_seconds=retry_chunk_seconds,
            batch_size=batch_size,
            generate_kwargs=generate_kwargs,
            warnings=warnings,
        )
        return result, {"segment_seconds": segment_seconds, "segments": [truncation]}

    boundaries: list[tuple[float, float]] = []
    start = 0.0
    while start < audio_duration:
        end = min(audio_duration, start + segment_seconds)
        boundaries.append((start, end))
        start = end

    all_chunks: list[dict] = []
    text_parts: list[str] = []
    segment_diagnostics: list[dict] = []
    for idx, (seg_start, seg_end) in enumerate(boundaries):
        segment_path = audio_path.with_name(f"{audio_path.stem}_segment_{idx:03d}.wav")
        try:
            write_wav_slice(audio_path, segment_path, seg_start, seg_end)
            result, truncation = _run_asr_with_retry(
                asr,
                segment_path,
                initial_chunk_seconds=initial_chunk_seconds,
                retry_chunk_seconds=retry_chunk_seconds,
                batch_size=batch_size,
                generate_kwargs=generate_kwargs,
                warnings=warnings,
            )
            shifted = shift_chunk_timestamps(result, seg_start)
            all_chunks.extend(shifted.get("chunks") or [])
            segment_text = (result.get("text") or "").strip()
            if segment_text:
                text_parts.append(segment_text)
            segment_diagnostics.append({"segment_index": idx, "start": seg_start, "end": seg_end, **truncation})
        finally:
            try:
                segment_path.unlink()
            except OSError:
                pass
            _free_cuda_cache()

    merged = {"text": " ".join(text_parts), "chunks": all_chunks}
    return merged, {"segment_seconds": segment_seconds, "segments": segment_diagnostics}


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
        "max_new_tokens": MAX_NEW_TOKENS,
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


def retry_if_truncated(
    asr,
    audio_path: Path,
    result: dict,
    initial_chunk_seconds: float,
    retry_chunk_seconds: float,
    batch_size: int,
    generate_kwargs: dict,
    warnings: list[str],
) -> tuple[dict, dict]:
    audio_duration = wav_duration_seconds(audio_path)
    chunks = result.get("chunks") or []
    words = words_from_chunks(chunks, [])
    suspicion = detect_truncation_suspicion(result, words, audio_duration, initial_chunk_seconds)
    diagnostics = {
        "suspected": suspicion.suspected,
        "retried": False,
        "initial_chunk_seconds": initial_chunk_seconds,
        "retry_chunk_seconds": retry_chunk_seconds,
        "reason": suspicion.reason,
        "retry_start": suspicion.retry_start,
        "retry_end": suspicion.retry_end,
        "final_status": "not_suspected",
    }
    if not suspicion.suspected:
        return result, diagnostics
    warnings.append(
        "Possible Whisper truncation detected"
        + (f" ({suspicion.reason})" if suspicion.reason else "")
        + "; retrying only the suspected audio range with a smaller chunk."
    )
    diagnostics["retried"] = True
    retry_path = audio_path.with_name(audio_path.stem + "_truncation_retry.wav")
    try:
        write_wav_slice(audio_path, retry_path, float(suspicion.retry_start or 0.0), float(suspicion.retry_end or audio_duration))
        retry_result = run_asr(
            asr,
            retry_path,
            chunk_length_s=retry_chunk_seconds,
            batch_size=batch_size,
            generate_kwargs=generate_kwargs,
        )
        shifted_retry = shift_chunk_timestamps(retry_result, float(suspicion.retry_start or 0.0))
        merged = merge_retry_result(result, shifted_retry, float(suspicion.retry_start or 0.0))
        retry_words = words_from_chunks(shifted_retry.get("chunks") or [], [])
        followup = detect_truncation_suspicion(merged, words_from_chunks(merged.get("chunks") or [], []), audio_duration, retry_chunk_seconds)
        if followup.suspected and retry_words:
            warnings.append("Whisper truncation is still suspected after retry; outputs were kept with a warning.")
            diagnostics["final_status"] = "warning_after_retry"
        elif retry_words:
            diagnostics["final_status"] = "retry_success"
        else:
            warnings.append("Whisper truncation retry produced no additional timestamped words.")
            diagnostics["final_status"] = "retry_no_words"
        return merged, diagnostics
    except Exception as exc:
        warnings.append(f"Whisper truncation retry could not run: {exc}")
        diagnostics["final_status"] = "retry_failed"
        return result, diagnostics
    finally:
        try:
            retry_path.unlink()
        except OSError:
            pass


def detect_truncation_suspicion(
    result: dict,
    words: list[TranscriptWord],
    audio_duration: float | None,
    chunk_length_s: float,
) -> TruncationSuspicion:
    if not audio_duration or audio_duration <= 0:
        return TruncationSuspicion(False)
    if token_limit_reached(result, MAX_NEW_TOKENS):
        retry_start = max(0.0, (words[-1].end if words else 0.0) - 0.5)
        return TruncationSuspicion(True, "max_new_tokens", retry_start, audio_duration)
    text = (result.get("text") or "").strip()
    if not text or not words:
        return TruncationSuspicion(False)
    last_end = max(word.end for word in words)
    early_gap = audio_duration - last_end
    grace = max(EARLY_END_GRACE_SECONDS, min(8.0, chunk_length_s * 0.25))
    if audio_duration >= chunk_length_s * 0.8 and early_gap > grace:
        return TruncationSuspicion(True, "early_timestamp_end", max(0.0, last_end - 0.5), audio_duration)
    return TruncationSuspicion(False)


def token_limit_reached(result: dict, max_new_tokens: int) -> bool:
    if bool(result.get("token_limit_reached") or result.get("max_new_tokens_reached")):
        return True
    if result.get("finish_reason") == "length":
        return True
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    if bool(metadata.get("token_limit_reached") or metadata.get("max_new_tokens_reached")):
        return True
    for key in ("generated_tokens", "num_generated_tokens", "token_count"):
        value = result.get(key, metadata.get(key))
        if isinstance(value, int) and value >= max_new_tokens:
            return True
    return False


def wav_duration_seconds(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / rate if rate else None
    except (wave.Error, OSError, EOFError):
        return None


def write_wav_slice(source: Path, target: Path, start: float, end: float) -> None:
    if end <= start:
        raise ValueError(f"invalid retry audio range: {start:.3f}-{end:.3f}s")
    with wave.open(str(source), "rb") as src:
        rate = src.getframerate()
        start_frame = max(0, int(start * rate))
        end_frame = min(src.getnframes(), int(end * rate))
        if end_frame <= start_frame:
            raise ValueError(f"empty retry audio range: {start:.3f}-{end:.3f}s")
        src.setpos(start_frame)
        frames = src.readframes(end_frame - start_frame)
        with wave.open(str(target), "wb") as dst:
            dst.setnchannels(src.getnchannels())
            dst.setsampwidth(src.getsampwidth())
            dst.setframerate(rate)
            dst.writeframes(frames)


def shift_chunk_timestamps(result: dict, offset: float) -> dict:
    shifted = dict(result)
    shifted_chunks: list[dict] = []
    for chunk in result.get("chunks") or []:
        item = dict(chunk)
        start, end = item.get("timestamp") or (None, None)
        if start is not None and end is not None:
            item["timestamp"] = (float(start) + offset, float(end) + offset)
        shifted_chunks.append(item)
    shifted["chunks"] = shifted_chunks
    return shifted


def merge_retry_result(original: dict, retry: dict, retry_start: float) -> dict:
    original_chunks = [chunk for chunk in (original.get("chunks") or []) if chunk_starts_before(chunk, retry_start)]
    retry_chunks = retry.get("chunks") or []
    merged = dict(original)
    merged["chunks"] = original_chunks + retry_chunks
    merged["text"] = " ".join(part for part in ((original.get("text") or "").strip(), (retry.get("text") or "").strip()) if part)
    merged["token_limit_reached"] = False
    merged["max_new_tokens_reached"] = False
    return merged


def chunk_starts_before(chunk: dict, timestamp: float) -> bool:
    start, _end = chunk.get("timestamp") or (None, None)
    return start is None or float(start) < timestamp


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
