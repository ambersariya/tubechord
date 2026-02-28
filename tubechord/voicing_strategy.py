"""VoicingStrategy: Strategy pattern for mapping chord events to MIDI note sets."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from tubechord.chord_analyzer import ChordEvent

# ── MIDI constants ──────────────────────────────────────────────────────────
SEMITONES_PER_OCTAVE = 12
MIDDLE_C_MIDI = 60  # C4 in Scientific Pitch Notation


def pitch_class_to_midi(pitch_class: int, octave: int) -> int:
    """
    Convert a pitch class (0-11) and an octave number to an absolute MIDI note.

    MIDI octave numbering: C-1 = 0, C0 = 12, C1 = 24, ... C4 (Middle C) = 60.

    Args:
        pitch_class: 0=C, 1=C#, 2=D, ..., 11=B.
        octave:      Scientific octave number (e.g. 4 for Middle C octave).

    Returns:
        MIDI note number.
    """
    return (octave + 1) * SEMITONES_PER_OCTAVE + pitch_class


@dataclass
class VoicedChord:
    """
    A chord event annotated with concrete MIDI note assignments.

    Attributes:
        event:            The original ChordEvent (root, type, timing).
        right_hand_notes: MIDI note numbers for the right hand (treble, Track 1).
        left_hand_notes:  MIDI note numbers for the left hand (bass, Track 0).
                          Empty list for Grade 1.
    """

    event: ChordEvent
    right_hand_notes: list[int] = field(default_factory=list)
    left_hand_notes: list[int] = field(default_factory=list)


# ── Interval tables ─────────────────────────────────────────────────────────

#: Root position major triad: root, major-3rd (+4), perfect-5th (+7)
MAJOR_INTERVALS: list[int] = [0, 4, 7]

#: Root position minor triad: root, minor-3rd (+3), perfect-5th (+7)
MINOR_INTERVALS: list[int] = [0, 3, 7]


# ── Abstract base ────────────────────────────────────────────────────────────

class VoicingStrategy(ABC):
    """
    Abstract Strategy for assigning MIDI pitches to a detected chord.

    Concrete subclasses implement ``voice()`` to produce different note
    layouts suitable for different piano difficulty levels.
    """

    def _get_intervals(self, chord_type: str) -> list[int]:
        """Return the semitone intervals for a major or minor triad."""
        return MAJOR_INTERVALS if chord_type == "major" else MINOR_INTERVALS

    @abstractmethod
    def voice(self, event: ChordEvent) -> VoicedChord:
        """
        Map a ChordEvent to a VoicedChord with concrete MIDI note numbers.

        Args:
            event: Detected chord event with root, type, and timing.

        Returns:
            VoicedChord with right_hand_notes and left_hand_notes populated.
        """


# ── Concrete strategies ──────────────────────────────────────────────────────

class Grade1Voicer(VoicingStrategy):
    """
    Grade 1 voicing: root-position triads in the Middle C octave (C4).

    Right hand only — no bass notes, keeping things simple for beginners.

    MIDI note ranges
    ----------------
    All three chord tones live in octave 4 or just above it:

        Lowest possible chord  : C major  → C4(60), E4(64),  G4(67)
        Highest possible chord : B major  → B4(71), D#5(75), F#5(78)
        Minor example          : A minor  → A4(69), C5(72),  E5(76)

    The right-hand span never exceeds a major 6th above the root,
    keeping the notes well within a beginner's comfortable reach.
    """

    RH_OCTAVE = 4  # Middle C octave — C4 = MIDI 60

    def voice(self, event: ChordEvent) -> VoicedChord:
        intervals = self._get_intervals(event.chord_type)
        root_midi = pitch_class_to_midi(event.root, self.RH_OCTAVE)
        right_hand = [root_midi + iv for iv in intervals]

        return VoicedChord(
            event=event,
            right_hand_notes=right_hand,
            left_hand_notes=[],
        )


class Grade2Voicer(VoicingStrategy):
    """
    Grade 2 voicing: root-position triads (RH) plus a single bass root (LH).

    The left hand plays the chord root one octave below the right-hand triad,
    introducing hand independence — a key milestone for Grade 2 learners.

    MIDI note ranges
    ----------------
    Left hand (Track 0, octave 3):

        C3 = MIDI 48  …  B3 = MIDI 59

    Right hand (Track 1, octave 4):

        C4 = MIDI 60  …  F#5 = MIDI 78  (highest 5th of B major)

    The octave separation gives the MIDI file a clear two-voice texture,
    making it easy to mute one track in a MIDI player for isolated practice.
    """

    RH_OCTAVE = 4  # Right hand: C4 = MIDI 60
    LH_OCTAVE = 3  # Left hand:  C3 = MIDI 48  (one octave below RH root)

    def voice(self, event: ChordEvent) -> VoicedChord:
        intervals = self._get_intervals(event.chord_type)
        root_rh = pitch_class_to_midi(event.root, self.RH_OCTAVE)
        root_lh = pitch_class_to_midi(event.root, self.LH_OCTAVE)

        right_hand = [root_rh + iv for iv in intervals]
        left_hand = [root_lh]

        return VoicedChord(
            event=event,
            right_hand_notes=right_hand,
            left_hand_notes=left_hand,
        )
