from bibl_windows.audio.presets import build_audio_filter_chain
from bibl_windows.timeline.models import TimeRange


def test_audio_preset_contains_noise_and_deesser():
    chain = build_audio_filter_chain("podcast", noise_floor_db=-42.4)
    assert "afftdn" in chain
    assert "deesser" in chain
    assert "loudnorm" in chain


def test_audio_filter_adds_breath_volume_ranges():
    chain = build_audio_filter_chain("natural", breath_ranges=[TimeRange(1, 1.5)])
    assert "between(t,1.000,1.500)" in chain
    assert "volume=0.38" in chain
