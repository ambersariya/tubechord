"""SheetExporter: converts MIDI files to HTML or Markdown sheet outputs."""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any, Final

from tubechord.sheet_models import ScoreDocument, VexflowMeasure, VexflowNote
from tubechord.sheet_renderers import (
    SheetRenderer,
    VerovioHtmlRenderer,
    VexflowMarkdownRenderer,
)

SUPPORTED_FORMATS: Final[set[str]] = {"html", "md-vexflow"}


class SheetExporter:
    """
    Convert a MIDI file into sheet output via a pluggable renderer.

    Supported formats:
    - ``html``: MusicXML -> Verovio -> inline SVG in a self-contained HTML file.
    - ``md-vexflow``: markdown file with embedded VexFlow JavaScript renderer.
    """

    _DURATION_MAP: Final[list[tuple[float, str]]] = [
        (4.0, "w"),
        (3.0, "hd"),
        (2.0, "h"),
        (1.5, "qd"),
        (1.0, "q"),
        (0.75, "8d"),
        (0.5, "8"),
        (0.25, "16"),
    ]

    def __init__(self, title: str = "", output_format: str = "html") -> None:
        self.title = title
        normalized = output_format.strip().lower()
        if normalized not in SUPPORTED_FORMATS:
            supported = ", ".join(sorted(SUPPORTED_FORMATS))
            raise ValueError(f"Unsupported output format '{output_format}'. Use one of: {supported}.")
        self.output_format = normalized
        self.renderer = self._build_renderer(normalized)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_renderer(self, output_format: str) -> SheetRenderer:
        if output_format == "html":
            return VerovioHtmlRenderer()
        return VexflowMarkdownRenderer()

    def _parse_midi_score(self, midi_path: str) -> Any:
        from music21 import converter

        return converter.parse(midi_path, format="midi")

    def _remove_empty_parts(self, score: Any) -> None:
        """Remove parts that contain no notes/chords to avoid blank staves."""
        for part in list(score.parts):
            if not part.flatten().notes:
                score.remove(part)

    def _score_to_musicxml_bytes(self, score: Any) -> bytes:
        from music21.musicxml.m21ToXml import GeneralObjectExporter

        exporter = GeneralObjectExporter(score)
        return exporter.parse()

    def _score_to_document(self, score: Any) -> ScoreDocument:
        measured_score = score.makeMeasures(inPlace=False)
        parts = list(measured_score.parts)

        time_signature = self._extract_time_signature(measured_score)
        beats, beat_value = self._parse_time_signature(time_signature)

        treble_part = parts[0] if parts else None
        bass_part = parts[1] if len(parts) > 1 else None

        treble_measures = self._extract_measures(treble_part)
        bass_measures = self._extract_measures(bass_part)
        measure_count = max(len(treble_measures), len(bass_measures), 1)

        measures: list[VexflowMeasure] = []
        for idx in range(measure_count):
            treble_measure = treble_measures[idx] if idx < len(treble_measures) else None
            bass_measure = bass_measures[idx] if idx < len(bass_measures) else None
            measures.append(
                VexflowMeasure(
                    treble=self._measure_to_notes(treble_measure, clef="treble"),
                    bass=self._measure_to_notes(bass_measure, clef="bass"),
                )
            )

        return ScoreDocument(
            title=self.title,
            time_signature=time_signature,
            beats=beats,
            beat_value=beat_value,
            measures=measures,
        )

    def _extract_time_signature(self, score: Any) -> str:
        for ts in score.recurse().getElementsByClass("TimeSignature"):
            ratio = getattr(ts, "ratioString", None)
            if isinstance(ratio, str) and ratio:
                return ratio
        return "4/4"

    def _parse_time_signature(self, time_signature: str) -> tuple[int, int]:
        match = re.match(r"^(\d+)/(\d+)$", time_signature.strip())
        if not match:
            return 4, 4
        beats = max(1, int(match.group(1)))
        beat_value = max(1, int(match.group(2)))
        return beats, beat_value

    def _extract_measures(self, part: Any | None) -> list[Any]:
        if part is None:
            return []
        measures = list(part.getElementsByClass("Measure"))
        return measures

    def _measure_to_notes(self, measure: Any | None, clef: str) -> list[VexflowNote]:
        if measure is None:
            return [self._default_rest(clef)]

        notes: list[VexflowNote] = []
        for element in measure.notesAndRests:
            quarter_length = float(Fraction(element.duration.quarterLength))
            duration = self._quarter_length_to_duration(quarter_length)

            if element.isRest:
                if clef == "treble":
                    keys = ["b/4"]
                else:
                    keys = ["d/3"]
                notes.append(
                    VexflowNote(
                        keys=keys,
                        duration=f"{duration}r",
                        accidentals=[None],
                    )
                )
                continue

            if element.isChord:
                keys = [self._pitch_to_key(pitch) for pitch in element.pitches]
            else:
                keys = [self._pitch_to_key(element.pitch)]

            notes.append(
                VexflowNote(
                    keys=keys,
                    duration=duration,
                    accidentals=[self._extract_accidental(key) for key in keys],
                )
            )

        return notes or [self._default_rest(clef)]

    def _default_rest(self, clef: str) -> VexflowNote:
        if clef == "treble":
            return VexflowNote(keys=["b/4"], duration="wr", accidentals=[None])
        return VexflowNote(keys=["d/3"], duration="wr", accidentals=[None])

    def _quarter_length_to_duration(self, quarter_length: float) -> str:
        if quarter_length <= 0:
            return "q"

        _, duration = min(
            self._DURATION_MAP,
            key=lambda pair: abs(pair[0] - quarter_length),
        )
        return duration

    def _pitch_to_key(self, pitch: Any) -> str:
        name = str(getattr(pitch, "name", "C")).lower().replace("-", "b")
        octave_value = getattr(pitch, "octave", 4)
        octave = octave_value if isinstance(octave_value, int) else 4
        return f"{name}/{octave}"

    def _extract_accidental(self, key: str) -> str | None:
        pitch_name = key.split("/", maxsplit=1)[0]
        if len(pitch_name) <= 1:
            return None
        accidental = pitch_name[1:]
        if accidental in {"#", "b", "##", "bb", "n"}:
            return accidental
        return None

    # ------------------------------------------------------------------
    # Compatibility wrappers for existing tests/helpers
    # ------------------------------------------------------------------

    def _render_svgs(self, musicxml_bytes: bytes) -> list[str]:
        html_renderer = VerovioHtmlRenderer()
        return html_renderer.render_svgs(musicxml_bytes)

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _build_html(self, svgs: list[str]) -> str:
        html_renderer = VerovioHtmlRenderer()
        return html_renderer.build_html(self.title, svgs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, midi_path: str, output_path: str) -> None:
        """
        Convert a MIDI file into the selected sheet format and write it to disk.

        Raises:
            ValueError: If rendering fails or required data is missing.
            OSError: If the output file cannot be written.
        """
        score = self._parse_midi_score(midi_path)
        self._remove_empty_parts(score)

        if self.output_format == "html":
            content = self.renderer.render(
                title=self.title,
                musicxml_bytes=self._score_to_musicxml_bytes(score),
            )
        else:
            content = self.renderer.render(
                title=self.title,
                score_document=self._score_to_document(score),
            )

        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(content)
