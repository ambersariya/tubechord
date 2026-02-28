# TubeChord Handbook
### A Guide for Beginner Piano Players and Curious Developers

---

## Table of Contents

1. [User Guide](#1-user-guide)
   - [Prerequisites](#prerequisites)
   - [Installation with Poetry](#installation-with-poetry)
   - [Quick Start](#quick-start)
   - [All CLI Options](#all-cli-options)
   - [Example Workflows](#example-workflows)
2. [Technical Architecture](#2-technical-architecture)
   - [Component Overview](#component-overview)
   - [AudioProcessor](#audioprocessor)
   - [ChordAnalyzer](#chordanalyzer)
   - [VoicingStrategy Pattern](#voicingstrategy-pattern)
   - [MidiExporter](#midiexporter)
   - [Data Flow Diagram](#data-flow-diagram)
3. [Music Theory Appendix](#3-music-theory-appendix)
   - [What is a Chromagram?](#what-is-a-chromagram)
   - [The Semitone Logic: How Minor vs Major is Detected](#the-semitone-logic-how-minor-vs-major-is-detected)
   - [MIDI Note Ranges for Grade 1 vs Grade 2](#midi-note-ranges-for-grade-1-vs-grade-2)
   - [Root Position Triads Explained](#root-position-triads-explained)
   - [The Two-Track MIDI Layout](#the-two-track-midi-layout)
4. [Troubleshooting](#4-troubleshooting)
   - [Noisy Audio / Many Short Chords](#noisy-audio--many-short-chords)
   - [Complex Jazz or Chromatic Harmonies](#complex-jazz-or-chromatic-harmonies)
   - [Download Failures](#download-failures)
   - [No Chords Detected](#no-chords-detected)

---

## 1. User Guide

### Prerequisites

Before installing TubeChord, ensure the following are available on your system:

| Requirement | Purpose | Install |
|-------------|---------|---------|
| **Python 3.10+** | Runtime | [python.org](https://www.python.org) |
| **Poetry** | Dependency & packaging manager | `pip install poetry` |
| **ffmpeg** | Audio conversion (WAV extraction) | `brew install ffmpeg` *(macOS)* / `apt install ffmpeg` *(Linux)* |

> **Why ffmpeg?**
> `yt-dlp` downloads the best audio stream from YouTube (often `.webm` or `.m4a`)
> and then calls ffmpeg to convert it to `.wav`. Without ffmpeg the download step
> will fail with a "no audio postprocessor" error.

---

### Installation with Poetry

```bash
# 1. Clone the repository
git clone https://github.com/ambersariya/tubechord.git
cd tubechord

# 2. Install all dependencies into an isolated virtual environment
poetry install

# 3. Verify the CLI is available
poetry run tubechord --version
# tubechord, version 0.1.0
```

If you want to run `tubechord` without the `poetry run` prefix, activate the
virtual environment first:

```bash
poetry shell
tubechord --version
```

---

### Quick Start

```bash
# Grade 1 — right-hand triads only (simplest)
tubechord "https://www.youtube.com/watch?v=VIDEO_ID" --grade 1

# Grade 2 — triads + left-hand bass note
tubechord "https://www.youtube.com/watch?v=VIDEO_ID" --grade 2

# Save to a custom file and set a slower practice tempo
tubechord "https://youtu.be/VIDEO_ID" --grade 2 --output twinkle.mid --tempo 60
```

The output `.mid` file can be opened in:
- **GarageBand** (macOS / iOS) — free, shows piano roll
- **MuseScore** — free, converts MIDI to sheet music notation
- **VLC / Windows Media Player** — playback only
- **LMMS / Ableton** — full DAW control with per-track muting

---

### All CLI Options

```
Usage: tubechord [OPTIONS] URL

  TubeChord — extract piano chords from a YouTube video and save them as MIDI.

Arguments:
  URL  YouTube video URL to analyse (wrap in quotes if it contains &).

Options:
  --grade [1|2]        Piano grade level.
                         1 = right-hand triads only (Middle C octave).
                         2 = triads + left-hand bass note one octave lower.
                       [default: 1]
  -o, --output PATH    Destination MIDI file path.  [default: output.mid]
  --tempo INTEGER      Playback tempo in BPM.  [default: 80]
  --min-duration SECS  Minimum chord duration in seconds.
                       Increase for noisy audio or complex harmonies.
                       [default: 0.5]
  --version            Show the version and exit.
  -h, --help           Show this message and exit.
```

---

### Example Workflows

#### Beginner — learn a pop song (Grade 1)

```bash
tubechord "https://www.youtube.com/watch?v=VIDEO_ID" \
  --grade 1 \
  --output pop_song_grade1.mid \
  --tempo 70
```

Open `pop_song_grade1.mid` in MuseScore to see the chords written on the treble
staff. Practice playing the right-hand triads along with the recording.

#### Intermediate — add the bass (Grade 2)

```bash
tubechord "https://www.youtube.com/watch?v=VIDEO_ID" \
  --grade 2 \
  --output pop_song_grade2.mid \
  --tempo 80
```

In GarageBand: mute **Track 0 (Left Hand)** first and practise the right hand.
Then mute **Track 1 (Right Hand)** and practise the left-hand bass. Finally,
play both tracks together.

#### Handling a busy/fast song

```bash
tubechord "https://www.youtube.com/watch?v=VIDEO_ID" \
  --grade 1 \
  --min-duration 1.5 \
  --tempo 60
```

`--min-duration 1.5` discards any chord that lasts less than 1.5 seconds,
leaving only the main structural chords.

---

## 2. Technical Architecture

### Component Overview

TubeChord is built around four decoupled classes that each own exactly one
concern. Data flows sequentially through a pipeline:

```
YouTube URL
    │
    ▼
┌──────────────────┐
│  AudioProcessor  │  yt-dlp download → librosa Chroma STFT
└──────────────────┘
    │ chromagram (12 × N frames), hop_duration
    ▼
┌──────────────────┐
│  ChordAnalyzer   │  smoothing → root detection → major/minor logic → grouping
└──────────────────┘
    │ List[ChordEvent]
    ▼
┌──────────────────┐
│ VoicingStrategy  │  Grade1Voicer or Grade2Voicer
└──────────────────┘
    │ List[VoicedChord]  (MIDI note numbers assigned)
    ▼
┌──────────────────┐
│  MidiExporter    │  midiutil → 2-track .mid file
└──────────────────┘
    │
    ▼
output.mid
```

---

### AudioProcessor

**File:** `tubechord/audio_processor.py`

**Responsibilities:**
- Uses `yt-dlp` to download the best audio stream from any YouTube URL,
  bypassing ads and the browser UI entirely.
- Invokes ffmpeg (via yt-dlp's post-processor) to transcode the stream to WAV.
- Loads the WAV with `librosa.load()` (resampled to mono).
- Computes a **Chroma STFT** with `librosa.feature.chroma_stft()`.
- Acts as a context manager (`with AudioProcessor() as p:`) to guarantee that
  the temporary WAV file and directory are deleted after processing, even if an
  exception occurs.

**Key parameters:**

| Parameter | Default | Effect |
|-----------|---------|--------|
| `hop_length` | 512 | Frames per step. Smaller = finer time resolution, slower. |
| `n_fft` | 2048 | FFT window size. Larger = better frequency resolution. |

**Why Chroma STFT?**
A regular spectrogram has hundreds of frequency bins. The chroma transform
collapses all of those bins into exactly **12 buckets** — one per semitone of
the chromatic scale (C, C#, D, … B), summing energy across all octaves. This
makes chord detection feasible with simple arithmetic instead of machine
learning.

---

### ChordAnalyzer

**File:** `tubechord/chord_analyzer.py`

**Responsibilities:**
- Applies temporal smoothing to the raw chromagram.
- For each frame, determines the root pitch class and chord type (major/minor).
- Merges consecutive identical frames into `ChordEvent` objects.
- Filters out events shorter than `min_chord_duration`.

**Data class — `ChordEvent`:**

```python
@dataclass
class ChordEvent:
    root: int        # 0=C, 1=C#, ..., 11=B
    chord_type: str  # "major" or "minor"
    start_time: float
    duration: float
    name: str        # property, e.g. "Am", "G", "F#m"
```

See the [Music Theory Appendix](#3-music-theory-appendix) for a detailed
explanation of the detection algorithm.

---

### VoicingStrategy Pattern

**File:** `tubechord/voicing_strategy.py`

This is the most educationally interesting part of the codebase. It uses the
**Strategy design pattern**: an abstract base class defines the interface, and
each concrete subclass provides a different algorithm for the same task
(assigning MIDI pitches to a chord).

```
         ┌────────────────────────┐
         │   VoicingStrategy      │  ← Abstract Base Class
         │  ─────────────────     │
         │  + voice(event)        │  ← Abstract method
         └────────────────────────┘
                    ▲
         ┌──────────┴────────────┐
         │                       │
┌────────────────┐     ┌──────────────────┐
│  Grade1Voicer  │     │  Grade2Voicer    │
│ ─────────────  │     │ ───────────────  │
│ RH octave 4    │     │ RH octave 4      │
│ LH: empty      │     │ LH octave 3      │
└────────────────┘     └──────────────────┘
```

**Why Strategy?**
Adding a Grade 3 voicing (e.g. seventh chords) or a "simplified" voicing
(root + fifth only) requires writing one new class and passing it to the CLI —
no existing code changes needed. This is the **Open/Closed Principle** in practice.

**`VoicedChord` data class:**

```python
@dataclass
class VoicedChord:
    event: ChordEvent
    right_hand_notes: list[int]  # MIDI note numbers → Track 1
    left_hand_notes:  list[int]  # MIDI note numbers → Track 0
```

---

### MidiExporter

**File:** `tubechord/midi_exporter.py`

**Responsibilities:**
- Creates a **Standard MIDI File (SMF) Type 1** with two independent tracks.
- Converts `start_time` and `duration` (seconds) to beats using the formula:
  `beats = seconds × (tempo / 60)`.
- Writes left-hand notes to **Track 0, Channel 0** and right-hand notes to
  **Track 1, Channel 1**.
- Uses `midiutil.MIDIFile` for reliable SMF serialisation.

**Why two separate tracks?**
Any MIDI player or DAW can independently mute, solo, transpose, or change the
instrument on each track. This is crucial for beginner practice:
- Mute Track 0 → practise right hand only.
- Mute Track 1 → practise left hand only.
- Both tracks → full two-hand playback.

---

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ YouTube URL                                                          │
│    │                                                                 │
│    ▼  yt-dlp                                                        │
│ audio.wav (temp, auto-deleted)                                       │
│    │                                                                 │
│    ▼  librosa.load() + chroma_stft()                                │
│ chroma: np.ndarray[12, N_frames]   hop_duration: float (seconds)    │
│    │                                                                 │
│    ▼  ChordAnalyzer.analyze()                                       │
│ [ChordEvent(root=0, type='major', start=0.0, dur=2.4),              │
│  ChordEvent(root=9, type='minor', start=2.4, dur=1.8), ...]         │
│    │                                                                 │
│    ▼  Grade1Voicer.voice() or Grade2Voicer.voice()                 │
│ [VoicedChord(rh=[60,64,67], lh=[]),                                 │
│  VoicedChord(rh=[69,72,76], lh=[57]), ...]                          │
│    │                                                                 │
│    ▼  MidiExporter.export()                                         │
│ output.mid  (Track 0: bass | Track 1: chords)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Music Theory Appendix

### What is a Chromagram?

A **chromagram** (or chroma feature matrix) is a two-dimensional array with:
- **Rows (12):** one for each of the 12 semitones in Western music —
  C, C#, D, D#, E, F, F#, G, G#, A, A#, B.
- **Columns (N frames):** one snapshot every `hop_length` audio samples
  (≈ 23 ms at 22 050 Hz with `hop_length=512`).

Each cell contains a value between 0 and 1 representing how much energy the
recording has at that pitch class at that moment. Octave information is
collapsed — a C2 bass note and a C5 melody note both add to the "C" row.

```
Pitch  │ Frame 0 │ Frame 1 │ Frame 2 │ …
───────┼─────────┼─────────┼─────────┼──
C      │  0.85   │  0.80   │  0.10   │
C#     │  0.05   │  0.04   │  0.08   │
D      │  0.12   │  0.10   │  0.05   │
D#     │  0.07   │  0.06   │  0.70   │   ← suddenly high → chord change
E      │  0.55   │  0.52   │  0.08   │
F      │  0.08   │  0.07   │  0.09   │
…      │  …      │  …      │  …      │
```

---

### The Semitone Logic: How Minor vs Major is Detected

This is the **"brain"** of TubeChord. Here is the full algorithm, step by step.

#### Step 1 — Find the Root

For each time frame, find the pitch class with the **maximum energy**:

```python
root = np.argmax(chroma_frame)   # integer 0–11
```

If frame 0 has its highest energy at index 0, the root is **C**.

#### Step 2 — Test the Third

The defining difference between a major and minor chord is the **third** —
the note sitting 3 or 4 semitones above the root:

| Interval above root | Name | Chord quality |
|---------------------|------|---------------|
| +3 semitones | Minor 3rd | Minor triad (e.g. C–E♭–G) |
| +4 semitones | Major 3rd | Major triad (e.g. C–E–G) |

TubeChord compares the chroma energy at these two positions:

```python
minor_third_energy = chroma_frame[(root + 3) % 12]
major_third_energy = chroma_frame[(root + 4) % 12]

if minor_third_energy > major_third_energy:
    chord_type = "minor"
else:
    chord_type = "major"
```

> **The modulo `% 12` wraps around the chromatic scale.**
> For root = A (index 9):
> - Minor 3rd: (9 + 3) % 12 = **0 → C** → A minor = A–C–E ✓
> - Major 3rd: (9 + 4) % 12 = **1 → C#** → A major = A–C#–E ✓

#### Concrete Example

Suppose the chroma vector for a frame is:

```
Index:  0    1    2    3    4    5    6    7    8    9   10   11
Note:   C   C#    D   D#    E    F   F#    G   G#    A   A#    B
Energy: 0.1  0.05 0.1 0.7  0.1  0.1 0.05 0.6  0.1  0.1 0.05 0.05
```

1. `root = argmax = 3` → **D#** (also written E♭)
2. Minor 3rd: index (3+3)%12 = **6 → F#** → energy = 0.05
3. Major 3rd: index (3+4)%12 = **7 → G** → energy = 0.60
4. 0.60 > 0.05 → **MAJOR** → chord is **E♭ major** (E♭–G–B♭)

#### Step 3 — Temporal Smoothing

Raw chroma features are noisy because:
- Drum hits create brief energy spikes in random pitch classes.
- Reverb tails from one chord "bleed" into the next frame.

TubeChord applies a **uniform (box) filter** along the time axis before
detection. It replaces each frame's value with the average of the surrounding
`smoothing_window` frames (default: 9 frames ≈ 0.2 seconds):

```python
kernel = np.ones(smoothing_window) / smoothing_window
smoothed = np.apply_along_axis(
    lambda row: np.convolve(row, kernel, mode="same"),
    axis=1,
    arr=chroma,
)
```

This removes brief transients without significantly blurring slow harmonic
changes, making the root detection much more stable.

#### Step 4 — Merging Frames into Events

After frame-by-frame detection, consecutive frames with the same `(root, type)`
are merged into a single `ChordEvent`. Events shorter than `--min-duration`
seconds are discarded. This prevents a single drum hit from producing a
phantom one-frame chord.

---

### MIDI Note Ranges for Grade 1 vs Grade 2

MIDI note numbers run from **0 (C-1)** to **127 (G9)**. Middle C is **C4 = MIDI 60**.

The `pitch_class_to_midi` helper computes:

```
midi_note = (octave + 1) × 12 + pitch_class
```

So C4 = (4+1) × 12 + 0 = **60** ✓

#### Grade 1 — Right Hand Only (Octave 4)

The root is placed in octave 4 (C4–B4). The entire triad stays within octave
4 or just crosses into octave 5:

| Chord | Notes | MIDI Numbers |
|-------|-------|-------------|
| C major | C4 – E4 – G4 | 60 – 64 – 67 |
| C minor | C4 – E♭4 – G4 | 60 – 63 – 67 |
| G major | G4 – B4 – D5 | 67 – 71 – 74 |
| A minor | A4 – C5 – E5 | 69 – 72 – 76 |
| B major | B4 – D#5 – F#5 | 71 – 75 – 78 |

Range summary: **MIDI 60 – 78** (C4 to F#5).

All notes are well within the right hand's comfortable reach for a Grade 1
student. The triad fits within a single hand position (no stretching beyond a
6th in most cases).

#### Grade 2 — Right Hand Triads + Left Hand Bass (Octave 3)

The right hand plays the same octave-4 triads as Grade 1. The left hand adds
the root note **one octave lower** in octave 3 (C3–B3):

| Chord | LH (Track 0) | RH (Track 1) | MIDI (LH) | MIDI (RH) |
|-------|-------------|-------------|-----------|-----------|
| C major | C3 | C4 – E4 – G4 | 48 | 60 – 64 – 67 |
| C minor | C3 | C4 – E♭4 – G4 | 48 | 60 – 63 – 67 |
| G major | G3 | G4 – B4 – D5 | 55 | 67 – 71 – 74 |
| A minor | A3 | A4 – C5 – E5 | 57 | 69 – 72 – 76 |

LH range: **MIDI 48 – 59** (C3 to B3).
RH range: **MIDI 60 – 78** (C4 to F#5).

The 12-semitone gap between the lowest right-hand note (60) and the highest
left-hand note (59) creates a natural register separation — exactly how a
beginner would play on a real piano.

---

### Root Position Triads Explained

A **triad** is a three-note chord built in stacked thirds. In **root position**:
- The **root** is the lowest note.
- The **third** is the middle note (3 or 4 semitones above the root).
- The **fifth** is the top note (always 7 semitones above the root).

```
Major triad (intervals: 0, +4, +7):        Minor triad (intervals: 0, +3, +7):

    E4 (64)  ─ 7th  ─┐                         Eb4 (63) ─ 7th  ─┐
    ...               │ Perfect 5th              ...               │ Perfect 5th
    G4 (67)  ─────────┘                         G4 (67)  ─────────┘
    C4 (60)  root                               C4 (60)  root

    C major: C–E–G                              C minor: C–Eb–G
```

Root position is the easiest voicing to read and play — it matches exactly what
is written in most beginner method books (e.g. Alfred's Basic Piano Library,
ABRSM Grade 1 pieces).

---

### The Two-Track MIDI Layout

```
Track 0 — Left Hand (Bass)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ○──────────┐  ○──────────┐  ○────┐  ○────────────┐
  C3         │  G3         │  F3   │  A3            │
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Track 1 — Right Hand (Chords)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ○──────────┐  ○──────────┐  ○────┐  ○────────────┐   G4/E5/C5
  ○──────────┐  ○──────────┐  ○────┐  ○────────────┐   E4/B4/A4
  ○──────────┐  ○──────────┐  ○────┐  ○────────────┐   C4/G4/F4
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  C maj       G maj         F maj   A min
```

In GarageBand or MuseScore you can:
1. **Solo Track 1** → hear only the chords. Play along with the right hand.
2. **Solo Track 0** → hear only the bass. Play along with the left hand.
3. **Play both** → full two-hand texture.

---

## 4. Troubleshooting

### Noisy Audio / Many Short Chords

**Symptom:** The output MIDI contains dozens of very brief chords that change
every half-second, making it unplayable.

**Cause:** Percussive sounds (drums, claps), fast runs, or dense instrumentation
create rapid energy fluctuations across pitch classes.

**Solutions:**

1. **Increase `--min-duration`** (most effective first step):
   ```bash
   tubechord URL --min-duration 1.5
   ```
   This discards any chord shorter than 1.5 seconds, keeping only the
   structural harmonic pillars of the song.

2. **Increase `smoothing_window`** in `ChordAnalyzer` (code-level change):
   ```python
   analyzer = ChordAnalyzer(min_chord_duration=1.0, smoothing_window=21)
   ```
   A window of 21 frames smooths over ~0.5 seconds of audio at the default
   settings, heavily suppressing percussion transients.

3. **Choose a simpler song:** Songs with a clear guitar or piano accompaniment
   (e.g. solo acoustic recordings) work far better than full-band pop
   productions with heavy compression and reverb.

---

### Complex Jazz or Chromatic Harmonies

**Symptom:** The chords detected sound "wrong" — the MIDI does not match the
actual chords in the song.

**Cause:** TubeChord's detector is built for **triads** (3-note chords). Jazz
frequently uses:
- **7th chords** (e.g. Cmaj7, G7, Am7) — four notes.
- **Extended chords** (9ths, 11ths, 13ths) — five or more notes.
- **Altered chords** (e.g. G7#11, Eb7b9) — chromatic colour tones.
- **Polychords** — two different triads played simultaneously.

In these cases, multiple pitch classes have high energy simultaneously. The
`argmax` root-finder will pick the loudest one, which may not be the
functional root of the chord.

**Mitigation strategies:**

1. **Accept approximate chords.** For beginners, the detected chord is often
   a reasonable simplification. A Cmaj7 becomes "C major". A Dm7 becomes "D
   minor". These are good starting points for improvisation and ear training.

2. **Transpose to a simpler song.** The tool is designed for Grade 1–2 repertoire:
   folk songs, pop ballads, simple classical pieces. Complex jazz standards are
   outside its intended scope.

3. **Post-edit in MuseScore.** Import the MIDI, identify obviously wrong chords
   by listening, and correct them manually. The tool gives you 80% of the work
   done automatically.

4. **Future enhancement:** Replace the `argmax` + semitone comparison with a
   **template matching** approach — compare each frame's chroma vector against
   all 24 major/minor triad templates using cosine similarity. This is more
   robust to dense harmonies and is a natural next step if you want to extend
   the `ChordAnalyzer` class.

---

### Download Failures

**Symptom:**
```
ERROR: Could not download audio — ...
```

**Common causes and fixes:**

| Error message | Fix |
|--------------|-----|
| `ffmpeg not found` | Install ffmpeg: `brew install ffmpeg` |
| `Video unavailable` | The video is geo-blocked or private. Try a different video. |
| `Sign in to confirm your age` | Age-restricted content. yt-dlp may need cookies. |
| `HTTP Error 429` | YouTube rate-limited your IP. Wait a few minutes and retry. |
| `This video is not available` | Region restriction. Use a VPN or different video. |

To update yt-dlp (fixes most transient issues):
```bash
pip install -U yt-dlp
```

---

### No Chords Detected

**Symptom:**
```
WARNING: No chords detected. Try lowering --min-duration or checking the audio source.
```

**Cause:** All detected chord events are shorter than `--min-duration`.

**Fix:** Lower the threshold:
```bash
tubechord URL --min-duration 0.2
```

If the problem persists, the audio may be entirely percussive (e.g. a drum-only
track) with no tonal content for chroma analysis to work with.

---

*Handbook written for TubeChord v0.1.0 — Python 3.10+ / Poetry.*
