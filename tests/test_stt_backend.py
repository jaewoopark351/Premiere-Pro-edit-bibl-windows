from bibl_windows.stt.transformers_whisper import build_generate_kwargs, words_from_chunks


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
