"""ChordAnalyzer: Maps chroma energy vectors to Major/Minor triad events."""

from dataclasses import dataclass

import numpy as np

# Chromatic pitch class names (index 0 = C)
NOTE_NAMES: list[str] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@dataclass
class ChordEvent:
    """
    A single detected chord occurrence in the audio timeline.

    Attributes:
        root:       Pitch class of the chord root (0=C, 1=C#, ..., 11=B).
        chord_type: "major" or "minor".
        start_time: Start time in seconds.
        duration:   Duration in seconds.
    """

    root: int
    chord_type: str
    start_time: float
    duration: float

    @property
    def name(self) -> str:
        """Human-readable chord name, e.g. 'Am' or 'G'."""
        note = NOTE_NAMES[self.root]
        suffix = "m" if self.chord_type == "minor" else ""
        return f"{note}{suffix}"


class ChordAnalyzer:
    """
    Analyzes a chroma STFT matrix and returns a time-ordered list of ChordEvents.

    Algorithm overview
    ------------------
    For each chroma frame:

    1. **Root detection** – The pitch class (0-11) with the highest energy is
       treated as the chord root.

    2. **Major/Minor discrimination** – The semitone logic compares the energy
       at two intervals above the root:
         - Minor 3rd  (+3 semitones): characteristic of a minor triad.
         - Major 3rd  (+4 semitones): characteristic of a major triad.
       If energy[root + 3] > energy[root + 4]  →  MINOR chord.
       Otherwise                                →  MAJOR chord.

    3. **Temporal smoothing** – A box-filter pass reduces frame-to-frame jitter
       before step 1 and 2, producing more stable chord labels.

    4. **Grouping** – Consecutive frames with the same (root, type) are merged
       into a single ChordEvent. Events shorter than *min_chord_duration* are
       discarded as noise.
    """

    MINOR_THIRD = 3   # semitones above root for minor 3rd
    MAJOR_THIRD = 4   # semitones above root for major 3rd

    def __init__(
        self,
        min_chord_duration: float = 0.5,
        smoothing_window: int = 9,
    ) -> None:
        """
        Args:
            min_chord_duration: Discard chord events shorter than this (seconds).
                                Increase for noisy or complex audio.
            smoothing_window:   Width of the temporal smoothing kernel (frames).
                                Larger = more stable but blurs fast chord changes.
        """
        self.min_chord_duration = min_chord_duration
        self.smoothing_window = smoothing_window

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _smooth_chroma(self, chroma: np.ndarray) -> np.ndarray:
        """
        Apply a uniform (box) filter along the time axis of the chromagram.

        This averages each chroma bin over a sliding window of frames, which
        reduces per-frame noise without requiring scipy as a direct dependency
        (pure NumPy implementation).

        Args:
            chroma: shape (12, n_frames).

        Returns:
            Smoothed chromagram with the same shape.
        """
        kernel = np.ones(self.smoothing_window) / self.smoothing_window
        return np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="same"),
            axis=1,
            arr=chroma,
        )

    def _detect_frame_chord(self, chroma_frame: np.ndarray) -> tuple[int, str]:
        """
        Identify the (root, chord_type) for a single 12-element chroma vector.

        Args:
            chroma_frame: 1-D array of length 12 with energy per pitch class.

        Returns:
            (root_pitch_class, "major" | "minor")
        """
        root = int(np.argmax(chroma_frame))

        minor_third_energy = chroma_frame[(root + self.MINOR_THIRD) % 12]
        major_third_energy = chroma_frame[(root + self.MAJOR_THIRD) % 12]

        chord_type = "minor" if minor_third_energy > major_third_energy else "major"
        return root, chord_type

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, chroma: np.ndarray, hop_duration: float) -> list[ChordEvent]:
        """
        Analyse a chromagram and return a deduplicated list of chord events.

        Args:
            chroma:       Chromagram array of shape (12, n_frames).
            hop_duration: Duration of a single frame in seconds (hop_length / sr).

        Returns:
            List of ChordEvent objects ordered by start_time.
        """
        smoothed = self._smooth_chroma(chroma)
        n_frames = smoothed.shape[1]

        if n_frames == 0:
            return []

        # Detect chord for every frame
        frame_chords: list[tuple[int, str]] = [
            self._detect_frame_chord(smoothed[:, i]) for i in range(n_frames)
        ]

        # Merge consecutive identical chords into events
        chord_events: list[ChordEvent] = []
        current_root, current_type = frame_chords[0]
        current_start_frame = 0

        for i, (root, chord_type) in enumerate(frame_chords[1:], start=1):
            if root == current_root and chord_type == current_type:
                continue  # extend the current run

            # Emit the accumulated run
            run_duration = (i - current_start_frame) * hop_duration
            if run_duration >= self.min_chord_duration:
                chord_events.append(
                    ChordEvent(
                        root=current_root,
                        chord_type=current_type,
                        start_time=current_start_frame * hop_duration,
                        duration=run_duration,
                    )
                )

            current_root, current_type = root, chord_type
            current_start_frame = i

        # Emit the final run
        run_duration = (n_frames - current_start_frame) * hop_duration
        if run_duration >= self.min_chord_duration:
            chord_events.append(
                ChordEvent(
                    root=current_root,
                    chord_type=current_type,
                    start_time=current_start_frame * hop_duration,
                    duration=run_duration,
                )
            )

        return chord_events
