# Third Party Notices

## Premiere-Pro-edit-bibl

- Source repository: https://github.com/biblcontentofficial-art/Premiere-Pro-edit-bibl
- License: MIT
- Original copyright: Copyright (c) 2026 비블 (@bibl_youtube)

This Windows-first project is inspired by the original repository but is not a
direct platform-conditional port. The following original files were reviewed:

- `engine/silence_cut.py`
- `engine/make_subtitles.py`
- `engine/auto_cut.py`
- `engine/config.py`
- `engine/subtitle_polish.py`
- `engine/transcript_export.py`
- `engine/edit_diff.py`
- `engine/acoustic_filler.py`
- `engine/breath_reduce.py`
- `engine/analyze_video.py`
- `engine/shorts_xml.py`
- `engine/sync_2cam.py`
- `engine/mcam_xml.py`
- `engine/html_report.py`
- `README.md`
- `requirements.txt`
- `edit.sh`
- `batch.sh`

Adapted concepts:

- Silence and keep-range rough-cut strategy.
- FCP7 XML as a Premiere import format.
- Korean subtitle grouping and SRT timing cleanup ideas.
- Repetition and false-start detection concepts.
- Conservative/standard/aggressive preset concept.
- HTML review report concept.
- VTT/ASS/subtitle polish output concept.
- Transcript export and edit-diff report concept.
- Acoustic filler, breath detection, and noise-floor measurement concepts.
- Shorts XML, 2-camera sync, and multicam XML concepts.

MIT license notice from the original project is preserved in `LICENSE`.
