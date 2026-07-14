from pathlib import Path
from uuid import uuid4
import wave

from bibl_windows.stt.transformers_whisper import (
    detect_truncation_suspicion,
    retry_if_truncated,
    build_generate_kwargs,
    words_from_chunks,
)


class FakeTokenizer:
    def get_prompt_ids(self, prompt):
        return [1, len(prompt), 2]


class FakeAsr:
    tokenizer = FakeTokenizer()


def test_build_generate_kwargs_includes_verbatim_prompt_and_conditioning():
    warnings = []

    kwargs = build_generate_kwargs(
        FakeAsr(),
        language="ko",
        initial_prompt="어 음 반복 그대로",
        condition_on_previous_text=True,
        warnings=warnings,
    )

    assert kwargs["language"] == "ko"
    assert kwargs["task"] == "transcribe"
    assert kwargs["condition_on_prev_tokens"] is True
    assert kwargs["prompt_ids"].tolist() == [1, len("어 음 반복 그대로"), 2]
    assert warnings == []


def test_build_generate_kwargs_caps_max_new_tokens_to_bound_word_timestamp_memory():
    kwargs = build_generate_kwargs(
        FakeAsr(),
        language="ko",
        initial_prompt=None,
        condition_on_previous_text=True,
        warnings=[],
    )

    assert kwargs["max_new_tokens"] == 256


def test_words_from_chunks_skips_missing_timestamps_without_zero_fallback():
    warnings = []

    words = words_from_chunks(
        [
            {"text": "bad", "timestamp": (None, None)},
            {"text": "also bad", "timestamp": (0.0, 0.0)},
            {"text": "good", "timestamp": (1.0, 1.2)},
        ],
        warnings,
    )

    assert len(words) == 1
    assert words[0].text == "good"
    assert words[0].start == 1.0
    assert all(word.start != 0.0 or word.end != 0.0 for word in words)
    assert len(warnings) == 2


def test_detect_truncation_suspicion_from_token_limit_flag():
    words = words_from_chunks([{"text": "안녕", "timestamp": (1.0, 2.0)}], [])

    suspicion = detect_truncation_suspicion(
        {"text": "안녕", "chunks": [{"text": "안녕", "timestamp": (1.0, 2.0)}], "token_limit_reached": True},
        words,
        audio_duration=20.0,
        chunk_length_s=25.0,
    )

    assert suspicion.suspected is True
    assert suspicion.reason == "max_new_tokens"
    assert suspicion.retry_start == 1.5
    assert suspicion.retry_end == 20.0


def test_retry_if_truncated_retries_only_suspected_wav_range_with_smaller_chunk():
    root = Path(".test_tmp_manual") / f"stt-retry-{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    wav_path = root / "sample.wav"
    write_silent_wav(wav_path, duration=20.0)
    calls = []

    class FakeAsr:
        def __call__(self, audio_path, return_timestamps, chunk_length_s, batch_size, generate_kwargs):
            calls.append(
                {
                    "audio_path": Path(audio_path),
                    "return_timestamps": return_timestamps,
                    "chunk_length_s": chunk_length_s,
                    "batch_size": batch_size,
                    "generate_kwargs": generate_kwargs,
                }
            )
            return {
                "text": "뒤쪽",
                "chunks": [{"text": "뒤쪽", "timestamp": (17.0, 18.0)}],
            }

    result, diagnostics = retry_if_truncated(
        FakeAsr(),
        wav_path,
        {
            "text": "앞쪽",
            "chunks": [{"text": "앞쪽", "timestamp": (1.0, 2.0)}],
            "token_limit_reached": True,
        },
        initial_chunk_seconds=25.0,
        retry_chunk_seconds=12.5,
        batch_size=1,
        generate_kwargs={"max_new_tokens": 256},
        warnings=[],
    )

    assert len(calls) == 1
    assert calls[0]["audio_path"].name == "sample_truncation_retry.wav"
    assert calls[0]["chunk_length_s"] == 12.5
    words = words_from_chunks(result["chunks"], [])
    assert [(word.text, round(word.start, 1), round(word.end, 1)) for word in words] == [
        ("앞쪽", 1.0, 2.0),
        ("뒤쪽", 18.5, 19.5),
    ]
    assert diagnostics["suspected"] is True
    assert diagnostics["retried"] is True
    assert diagnostics["initial_chunk_seconds"] == 25.0
    assert diagnostics["retry_chunk_seconds"] == 12.5
    assert diagnostics["final_status"] == "retry_success"
    assert not calls[0]["audio_path"].exists()


def write_silent_wav(path: Path, duration: float, sample_rate: int = 16000) -> None:
    frames = int(duration * sample_rate)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"\x00\x00" * frames)
