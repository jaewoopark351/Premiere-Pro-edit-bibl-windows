from __future__ import annotations

from ..timeline.models import TimeRange


AUDIO_PRESETS = ("standard", "natural", "podcast")


def build_audio_filter_chain(
    preset: str = "standard",
    noise_floor_db: float | None = None,
    breath_ranges: list[TimeRange] | None = None,
) -> str:
    filters: list[str] = []
    nf = clamp_noise_floor(noise_floor_db)
    if preset == "podcast":
        filters.extend(
            [
                "highpass=f=90",
                f"afftdn=nf={nf}:nt=w",
                "deesser=i=0.35:m=0.6:f=0.5",
                "acompressor=threshold=-24dB:ratio=4:attack=4:release=120:makeup=3",
                "loudnorm=I=-14:TP=-1.5:LRA=9",
            ]
        )
    elif preset == "natural":
        filters.extend(
            [
                "highpass=f=70",
                f"afftdn=nf={nf}:nt=w",
                "deesser=i=0.25:m=0.5:f=0.5",
                "acompressor=threshold=-20dB:ratio=2.5:attack=5:release=160:makeup=1.5",
                "loudnorm=I=-16:TP=-1.5:LRA=11",
            ]
        )
    else:
        filters.extend(
            [
                "highpass=f=80",
                "acompressor=threshold=-20dB:ratio=3:attack=5:release=150:makeup=2",
                "loudnorm=I=-14:TP=-1.5:LRA=11",
            ]
        )
    for breath in (breath_ranges or [])[:80]:
        filters.append(f"volume=enable='between(t,{breath.start:.3f},{breath.end:.3f})':volume=0.38")
    return ",".join(filters)


def clamp_noise_floor(noise_floor_db: float | None) -> int:
    if noise_floor_db is None:
        return -35
    return int(max(-60, min(-25, round(noise_floor_db))))
