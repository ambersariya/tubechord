# TubeChord

Extract chords from a YouTube video and generate a MIDI file for beginner piano players (Grade 1–2).

## How It Works

1. Downloads audio from a YouTube URL via `yt-dlp`
2. Analyses the chromagram (12 pitch classes) using `librosa`
3. Detects chord root and quality (major/minor) via energy comparison
4. Voices chords to MIDI notes appropriate for the selected grade level
5. Exports a `.mid` file you can open in GarageBand, MuseScore, or any DAW

## Requirements

- Python 3.10+
- [Poetry](https://python-poetry.org/) 2.0+
- `ffmpeg` installed and on your `PATH` (required by `yt-dlp` for audio extraction)

## Installation

```bash
git clone https://github.com/ambersariya/tubechord.git
cd tubechord
poetry install
```

## Usage

```
tubechord [OPTIONS] URL
```

`URL` is the YouTube video to analyse. Wrap it in quotes if it contains `&`.

### Options

| Option | Default | Description |
|---|---|---|
| `--grade [1\|2]` | `1` | Grade 1: right-hand triads only. Grade 2: triads + left-hand bass note. |
| `-o`, `--output PATH` | `output.mid` | Destination MIDI file path. |
| `--tempo INT` | `80` | Playback tempo in BPM (20–300). |
| `--min-duration SECS` | `0.5` | Minimum chord duration in seconds. Raise to `1.0` for noisy audio. |
| `-V`, `--version` | | Show version and exit. |
| `-h`, `--help` | | Show help and exit. |

### Examples

```bash
# Grade 1 — right-hand triads, default tempo and output
tubechord "https://youtu.be/dQw4w9WgXcQ"

# Grade 2 — triads + bass, custom output file
tubechord "https://youtu.be/dQw4w9WgXcQ" --grade 2 -o my_song.mid

# Slower tempo, longer minimum chord duration for noisy audio
tubechord "https://youtu.be/dQw4w9WgXcQ" --grade 2 --tempo 60 --min-duration 1.0
```

### Sample Output

```
tubechord v0.1.0
  URL    : https://youtu.be/dQw4w9WgXcQ
  Grade  : 1  |  Tempo: 80 BPM  |  Output: output.mid

[1/4] Downloading audio from YouTube...
      Chroma shape : 4312 frames  (123.4 s)
[2/4] Analysing chord sequence...
      Detected 8 chord(s):
          0.00s  G     ================
          4.12s  Em    ============
          7.89s  C     ================
         12.01s  D     ============
         ...
[3/4] Applying Grade 1 voicing...
[4/4] Writing MIDI file → 'output.mid'...

Done!  Open 'output.mid' in GarageBand, MuseScore, or any MIDI player.
```

### Render Sheet Music From MIDI

Use the `sheet` subcommand to render notation from any `.mid` file:

```bash
# Default: self-contained HTML with inline SVG (verovio)
tubechord sheet my_song.mid

# Markdown with embedded VexFlow renderer
tubechord sheet my_song.mid --format md-vexflow -o my_song.md
```

## Grade Levels Explained

| Grade | Right Hand | Left Hand | MIDI Range |
|---|---|---|---|
| 1 | Triads (root position) in octave 4 | — | C4–F#5 |
| 2 | Triads (root position) in octave 4 | Bass note in octave 3 | C3–F#5 |

## Troubleshooting

**No chords detected**
Lower `--min-duration` (e.g. `--min-duration 0.2`) or verify the video contains clear harmonic content.

**Download fails**
Ensure `ffmpeg` is installed (`brew install ffmpeg` on macOS) and `yt-dlp` is up to date (`poetry run pip install -U yt-dlp`).

**MIDI sounds off-tempo**
Adjust `--tempo` to match the original song's BPM.

## License

MIT
