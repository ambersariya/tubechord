"""TubeChord CLI entry point."""

import re
import sys
from pathlib import Path

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


# ── CLI group ──────────────────────────────────────────────────────────────────

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(version=__version__, prog_name="tubechord")
def main() -> None:
    """TubeChord — YouTube chord extractor and sheet music generator."""


# ── extract subcommand ─────────────────────────────────────────────────────────

@main.command()
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
def extract(url: str, grade: int, output: str | None, tempo: int, min_duration: float) -> None:
    """
    Extract piano chords from a YouTube video and save them as MIDI.

    URL is the YouTube video to analyse (wrap in quotes if it contains &).

    \b
    Examples:
      tubechord extract "https://youtu.be/dQw4w9WgXcQ" --grade 1
      tubechord extract "https://youtu.be/dQw4w9WgXcQ" --grade 2 -o my_song.mid
      tubechord extract "https://youtu.be/dQw4w9WgXcQ" --grade 2 --tempo 60 --min-duration 1.0
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


# ── sheet subcommand ───────────────────────────────────────────────────────────

@main.command()
@click.argument("midi_file", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="PATH",
    help="Destination sheet file path. Defaults to extension based on --format.",
)
@click.option(
    "--title",
    default=None,
    metavar="TEXT",
    help="Title shown in the output header. Defaults to the MIDI filename stem.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["html", "md-vexflow"], case_sensitive=False),
    default="html",
    show_default=True,
    help="Sheet output format: self-contained HTML (verovio) or Markdown with VexFlow script.",
)
def sheet(
    midi_file: str,
    output: str | None,
    title: str | None,
    output_format: str,
) -> None:
    """
    Render a MIDI file as sheet music output (HTML or Markdown).

    MIDI_FILE is the path to an existing .mid file.
    - html: self-contained file with inline SVG sheet music.
    - md-vexflow: markdown with embedded VexFlow JavaScript renderer.

    \b
    Examples:
      tubechord sheet my_song.mid
      tubechord sheet my_song.mid -o score.html --title "My Song"
      tubechord sheet my_song.mid --format md-vexflow -o score.md
    """
    from tubechord.sheet_exporter import SheetExporter

    midi_path = Path(midi_file)
    resolved_title = title if title is not None else midi_path.stem.replace("_", " ")
    normalized_format = output_format.lower()
    default_suffix = ".html" if normalized_format == "html" else ".md"
    resolved_output = output if output is not None else str(midi_path.with_suffix(default_suffix))

    click.echo(f"tubechord v{__version__}")
    click.echo(f"  MIDI   : {midi_file}")
    click.echo(f"  Format : {normalized_format}")
    click.echo(f"  Title  : {resolved_title}")
    click.echo(f"  Output : {resolved_output}")
    click.echo()

    if normalized_format == "html":
        click.echo("[1/3] Parsing MIDI with music21...")
        click.echo("[2/3] Rendering notation to SVG with verovio...")
        click.echo("[3/3] Writing HTML file...")
    else:
        click.echo("[1/3] Parsing MIDI with music21...")
        click.echo("[2/3] Building VexFlow score payload...")
        click.echo("[3/3] Writing Markdown file...")

    exporter = SheetExporter(title=resolved_title, output_format=normalized_format)
    try:
        exporter.export(midi_file, resolved_output)
    except OSError as exc:
        click.echo(f"  ERROR: Could not write output file — {exc}", err=True)
        sys.exit(1)
    except ValueError as exc:
        click.echo(f"  ERROR: Could not render score — {exc}", err=True)
        sys.exit(1)

    click.echo()
    if normalized_format == "html":
        click.echo(f"Done!  Open '{resolved_output}' in any browser. Use Print → Save as PDF.")
    else:
        click.echo(
            f"Done!  Open '{resolved_output}' in a Markdown viewer that allows embedded JavaScript."
        )
