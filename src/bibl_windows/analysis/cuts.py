from __future__ import annotations

import difflib
import re
from dataclasses import replace

from ..timeline.models import CutCandidate, TimeRange, TranscriptWord


FILLER_WORDS = {
    "어",
    "음",
    "엄",
    "아",
    "그",
    "저",
    "좀",
    "약간",
    "그러니까",
    "그니까",
    "이제",
    "막",
}
SHORT_NOISE_WORDS = FILLER_WORDS | {"어어", "음음", "아아"}
AGGRESSIVE_AUTO_REASONS = {
    "short_meaningless_utterance",
    "hesitation_silence",
    "acoustic_filler",
    "false_start_prefix",
    "false_start_repeat",
}


def _norm(text: str) -> str:
    return re.sub(r"[^\w가-힣]", "", text).lower()


def silence_candidates(
    silences: list[TimeRange],
    total: float,
    long_silence: float,
    start_wait: float,
    end_silence: float,
    pad_before: float,
    pad_after: float,
) -> list[CutCandidate]:
    candidates: list[CutCandidate] = []
    for silence in silences:
        reason = None
        confidence = 0.75
        auto_delete = True
        if silence.start <= 0.25 and silence.duration >= start_wait:
            reason = "start_wait"
            confidence = 0.95
        elif total - silence.end <= 0.25 and silence.duration >= end_silence:
            reason = "end_long_silence"
            confidence = 0.95
        elif silence.duration >= long_silence:
            reason = "long_silence"
            confidence = 0.85
        if reason:
            start = max(0.0, silence.start + pad_before)
            end = min(total, silence.end - pad_after)
            if end > start:
                candidates.append(
                    CutCandidate(
                        start=start,
                        end=end,
                        reason=reason,
                        confidence=confidence,
                        auto_delete=auto_delete,
                        requires_review=False,
                        metadata={"source": "ffmpeg.silencedetect", "duration": silence.duration},
                    )
                )
    return candidates


def repeated_speech_candidates(words: list[TranscriptWord], max_gap: float, pad: float) -> list[CutCandidate]:
    out: list[CutCandidate] = []
    tokens = [_norm(w.text) for w in words]
    for size in (4, 3, 2):
        idx = 0
        while idx + size * 2 <= len(words):
            first = tokens[idx : idx + size]
            second = tokens[idx + size : idx + size * 2]
            gap = words[idx + size].start - words[idx + size - 1].end
            if all(first) and first == second and gap <= max_gap:
                out.append(
                    CutCandidate(
                        start=max(0.0, words[idx].start - pad),
                        end=min(words[idx + size].start, words[idx + size - 1].end + pad),
                        reason="repeated_phrase",
                        confidence=0.84,
                        auto_delete=True,
                        requires_review=False,
                        metadata={"text": " ".join(w.text for w in words[idx : idx + size]), "words": size},
                    )
                )
                idx += size * 2
            else:
                idx += 1
    idx = 0
    while idx < len(words) - 1:
        cur = tokens[idx]
        if cur and cur == tokens[idx + 1] and words[idx + 1].start - words[idx].end <= max_gap:
            start = max(0.0, words[idx].start - pad)
            end = min(words[idx + 1].start, words[idx].end + pad)
            out.append(
                CutCandidate(
                    start=start,
                    end=end,
                    reason="repeated_word",
                    confidence=0.88,
                    auto_delete=True,
                    requires_review=False,
                    metadata={"text": words[idx].text},
                )
            )
        idx += 1
    return out


def false_start_candidates(words: list[TranscriptWord], max_gap: float, pad: float, ratio: float) -> list[CutCandidate]:
    out: list[CutCandidate] = []
    tokens = [_norm(w.text) for w in words]
    for idx in range(len(words) - 1):
        first = tokens[idx]
        second = tokens[idx + 1]
        gap = words[idx + 1].start - words[idx].end
        is_prefix_restart = (
            first
            and second
            and first != second
            and gap <= max_gap
            and min(len(first), len(second)) >= 2
            and (first.startswith(second) or second.startswith(first))
        )
        if is_prefix_restart:
            out.append(
                CutCandidate(
                    start=max(0.0, words[idx].start - pad),
                    end=words[idx].end + pad,
                    reason="false_start_prefix",
                    confidence=0.68,
                    auto_delete=False,
                    requires_review=True,
                    metadata={"first": words[idx].text, "second": words[idx + 1].text},
                )
            )
    for size in (4, 3, 2):
        idx = 0
        while idx + size * 2 <= len(words):
            a = "".join(tokens[idx : idx + size])
            b = "".join(tokens[idx + size : idx + size * 2])
            gap = words[idx + size].start - words[idx + size - 1].end
            if a and b and a != b and gap <= max_gap and difflib.SequenceMatcher(None, a, b).ratio() >= ratio:
                out.append(
                    CutCandidate(
                        start=max(0.0, words[idx].start - pad),
                        end=words[idx + size - 1].end + pad,
                        reason="false_start_repeat",
                        confidence=0.72,
                        auto_delete=False,
                        requires_review=True,
                        metadata={"first": a, "second": b},
                    )
                )
                idx += size * 2
            else:
                idx += 1
    return out


def short_meaningless_candidates(words: list[TranscriptWord], max_duration: float, pad: float) -> list[CutCandidate]:
    out: list[CutCandidate] = []
    for idx, word in enumerate(words):
        token = _norm(word.text)
        if token in SHORT_NOISE_WORDS and word.end - word.start <= max_duration:
            protected_context = is_contextual_filler(token, words, idx)
            out.append(
                CutCandidate(
                    start=max(0.0, word.start - pad),
                    end=word.end + pad,
                    reason="short_meaningless_utterance",
                    confidence=0.65,
                    auto_delete=False,
                    requires_review=True,
                    metadata={"text": word.text, "protected_context": protected_context},
                )
            )
    return out


def hesitation_candidates(
    silences: list[TimeRange],
    words: list[TranscriptWord],
    min_duration: float,
    pad: float,
) -> list[CutCandidate]:
    if not silences or len(words) < 2:
        return []
    out: list[CutCandidate] = []
    ordered = sorted(words, key=lambda word: (word.start, word.end))
    for prev, nxt in zip(ordered, ordered[1:]):
        gap_start = prev.end
        gap_end = nxt.start
        if gap_end - gap_start < min_duration:
            continue
        for silence in silences:
            start = max(gap_start, silence.start) + pad
            end = min(gap_end, silence.end) - pad
            if end - start >= min_duration:
                out.append(
                    CutCandidate(
                        start=max(0.0, start),
                        end=end,
                        reason="hesitation_silence",
                        confidence=0.7,
                        auto_delete=False,
                        requires_review=True,
                        metadata={"source": "speech_gap", "previous": prev.text, "next": nxt.text},
                    )
                )
    return out


def apply_preset_policy(candidates: list[CutCandidate], preset_name: str, preset: dict) -> list[CutCandidate]:
    policy = preset.get("policy", {}) if isinstance(preset, dict) else {}
    auto_reasons = set(policy.get("auto_delete_reasons", []))
    if preset_name == "aggressive":
        auto_reasons |= AGGRESSIVE_AUTO_REASONS
    if not auto_reasons:
        return candidates
    out: list[CutCandidate] = []
    for candidate in candidates:
        protected_context = bool(candidate.metadata.get("protected_context"))
        if candidate.reason in auto_reasons and not protected_context:
            out.append(replace(candidate, auto_delete=True, requires_review=False))
        else:
            out.append(candidate)
    return out


def is_contextual_filler(token: str, words: list[TranscriptWord], idx: int) -> bool:
    if token != "좀":
        return False
    if idx + 1 >= len(words):
        return True
    nxt = _norm(words[idx + 1].text)
    degree_stems = (
        "더",
        "많",
        "많이",
        "빨리",
        "천천히",
        "조용",
        "길",
        "짧",
        "크",
        "작",
        "깊",
        "자주",
        "오래",
    )
    return not nxt or nxt.startswith(degree_stems)


def dedupe_candidates(candidates: list[CutCandidate]) -> list[CutCandidate]:
    candidates = sorted(candidates, key=lambda c: (c.start, c.end, c.reason))
    out: list[CutCandidate] = []
    for candidate in candidates:
        if out and candidate.start <= out[-1].end and candidate.reason == out[-1].reason:
            prev = out[-1]
            out[-1] = CutCandidate(
                start=min(prev.start, candidate.start),
                end=max(prev.end, candidate.end),
                reason=prev.reason,
                confidence=max(prev.confidence, candidate.confidence),
                auto_delete=prev.auto_delete and candidate.auto_delete,
                requires_review=prev.requires_review or candidate.requires_review,
                metadata={"merged": [prev.metadata, candidate.metadata]},
            )
        else:
            out.append(candidate)
    return out
