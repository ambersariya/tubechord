"""Data models for sheet music rendering outputs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VexflowNote:
    """A single VexFlow note or chord token."""

    keys: list[str]
    duration: str
    accidentals: list[str | None]


@dataclass(frozen=True)
class VexflowMeasure:
    """A pair of grand-staff voices for one measure."""

    treble: list[VexflowNote]
    bass: list[VexflowNote]


@dataclass(frozen=True)
class ScoreDocument:
    """Neutral score representation consumed by non-Verovio renderers."""

    title: str
    time_signature: str
    beats: int
    beat_value: int
    measures: list[VexflowMeasure]
