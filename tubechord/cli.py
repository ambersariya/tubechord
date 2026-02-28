"""TubeChord CLI entry point."""

import re
import sys

import click

from tubechord import __version__
from tubechord.audio_processor import AudioProcessor
from tubechord.chord_analyzer import ChordAnalyzer
from tubechord.midi_exporter import MidiExporter
from tubechord.voicing_strategy import Grade1Voicer, Grade2Voicer, VoicingStrategy

MAX_GRADE = 8


def _get_voicer(grade: int) -> VoicingStrategy:
    """Return the appropriate VoicingStrategy for the requested grade."""
    if grade == 1:
        return Grade1Voicer()
    return Grade2Voicer()


def _title_to_filename(title: str) -> str:
    """Convert a video title to a safe MIDI filename.

    Strips characters that are invalid in filenames, collapses whitespace to
    underscores, and appends the .mid extension.
    """
    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    return f"{sanitized}.mid"


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("url")
@click.option(
    "--grade",
    type=click.IntRange(1, MAX_GRADE),
    default=1,
    show_default=True,
    help=(
        f"Piano grade level (1–{MAX_GRADE}, ABRSM scale). "
        "Grade 1: right-hand triads only (Middle C octave). "
        "Grade 2+: triads + left-hand bass note one octave lower."
    ),
)
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="PATH",
    help="Destination MIDI file path. Defaults to <video-title>.mid.",
)
@click.option(
    "--tempo",
    type=click.IntRange(20, 300),
    default=80,
    show_default=True,
    help="Playback tempo in BPM.",
)
@click.option(
    "--min-duration",
    type=float,
    default=0.5,
    show_default=True,
    metavar="SECS",
    help=(
        "Minimum chord duration in seconds. "
        "Increase (e.g. 1.0) for noisy audio or complex harmonies."
    ),
)
@click.version_option(version=__version__, prog_name="tubechord")
def main(url: str, grade: int, output: str | None, tempo: int, min_duration: float) -> None:
    """
    TubeChord — extract piano chords from a YouTube video and save them as MIDI.

    URL is the YouTube video to analyse (wrap in quotes if it contains &).

    \b
    Examples:
      tubechord "https://youtu.be/dQw4w9WgXcQ" --grade 1
      tubechord "https://youtu.be/dQw4w9WgXcQ" --grade 2 -o my_song.mid
      tubechord "https://youtu.be/dQw4w9WgXcQ" --grade 2 --tempo 60 --min-duration 1.0
    """
    voicer = _get_voicer(grade)

    click.echo(f"tubechord v{__version__}")
    click.echo(f"  URL    : {url}")
    click.echo(f"  Grade  : {grade}  |  Tempo: {tempo} BPM")
    click.echo()

    with AudioProcessor() as processor:
        # ── Step 0: Resolve output filename ─────────────────────────────
        if output is None:
            click.echo("[0/4] Fetching video title...")
            try:
                title = processor.get_video_title(url)
                output = _title_to_filename(title)
            except Exception:
                output = "output.mid"
            click.echo(f"      Output   : {output}")
            click.echo()

        # ── Step 1: Download ────────────────────────────────────────────
        click.echo("[1/4] Downloading audio from YouTube...")
        try:
            chroma, hop_duration = processor.process(url)
        except FileNotFoundError as exc:
            click.echo(f"  ERROR: {exc}", err=True)
            sys.exit(1)
        except Exception as exc:
            click.echo(f"  ERROR: Could not download audio — {exc}", err=True)
            sys.exit(1)

        click.echo(f"      Chroma shape : {chroma.shape[1]} frames  "
                   f"({chroma.shape[1] * hop_duration:.1f} s)")

        # ── Step 2: Analyse chords ──────────────────────────────────────
        click.echo("[2/4] Analysing chord sequence...")
        analyzer = ChordAnalyzer(min_chord_duration=min_duration)
        chord_events = analyzer.analyze(chroma, hop_duration)

        if not chord_events:
            click.echo(
                "  WARNING: No chords detected. "
                "Try lowering --min-duration or checking the audio source.",
                err=True,
            )
            sys.exit(1)

        click.echo(f"      Detected {len(chord_events)} chord(s):")
        for event in chord_events:
            bar = "=" * int(event.duration * 4)
            click.echo(f"        {event.start_time:7.2f}s  {event.name:<4}  {bar}")

        # ── Step 3: Apply voicing ───────────────────────────────────────
        click.echo(f"[3/4] Applying Grade {grade} voicing...")
        voiced_chords = [voicer.voice(event) for event in chord_events]

        # ── Step 4: Export MIDI ─────────────────────────────────────────
        click.echo(f"[4/4] Writing MIDI file → '{output}'...")
        exporter = MidiExporter(tempo=tempo)
        try:
            exporter.export(voiced_chords, output)
        except OSError as exc:
            click.echo(f"  ERROR: Could not write MIDI file — {exc}", err=True)
            sys.exit(1)

    click.echo()
    click.echo(f"Done!  Open '{output}' in GarageBand, MuseScore, or any MIDI player.")
