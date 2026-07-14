from __future__ import annotations

import difflib
import re

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
    for word in words:
        token = _norm(word.text)
        if token in SHORT_NOISE_WORDS and word.end - word.start <= max_duration:
            out.append(
                CutCandidate(
                    start=max(0.0, word.start - pad),
                    end=word.end + pad,
                    reason="short_meaningless_utterance",
                    confidence=0.65,
                    auto_delete=False,
                    requires_review=True,
                    metadata={"text": word.text},
                )
            )
    return out


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
