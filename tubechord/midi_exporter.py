"""MidiExporter: Converts VoicedChord events into a 2-track MIDI file."""

from midiutil import MIDIFile

from tubechord.voicing_strategy import VoicedChord

# Track indices
TRACK_LH = 0  # Left Hand  / Bass  (Channel 0)
TRACK_RH = 1  # Right Hand / Chords (Channel 1)

# General MIDI channel assignments
CHANNEL_LH = 0
CHANNEL_RH = 1


class MidiExporter:
    """
    Writes a two-track MIDI file from a list of VoicedChord events.

    Track layout
    ------------
    Track 0 — "Left Hand (Bass)"
        Contains the left-hand bass note(s) produced by the VoicingStrategy.
        For Grade 1 this track is empty; for Grade 2 it holds the root note
        one octave below the right-hand triad.

    Track 1 — "Right Hand (Chords)"
        Contains the three-note triad produced by the VoicingStrategy.
        Both grade levels populate this track.

    This separation lets students mute one track in any standard MIDI player
    (GarageBand, MuseScore, etc.) to practise a single hand in isolation.

    Timing
    ------
    Chord start times and durations (in seconds, from ChordAnalyzer) are
    converted to beats using: beats = seconds × (tempo / 60).
    """

    DEFAULT_TEMPO = 80     # BPM — a comfortable practice tempo
    DEFAULT_VELOCITY = 80  # MIDI velocity for right-hand notes  (0-127)
    BASS_VELOCITY = 68     # Slightly softer left-hand bass notes

    def __init__(
        self,
        tempo: int = DEFAULT_TEMPO,
        velocity: int = DEFAULT_VELOCITY,
    ) -> None:
        """
        Args:
            tempo:    Playback tempo in beats per minute.
            velocity: MIDI note-on velocity for right-hand chord notes.
        """
        self.tempo = tempo
        self.velocity = velocity

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _seconds_to_beats(self, seconds: float) -> float:
        """Convert a time in seconds to beats at the current tempo."""
        return seconds * (self.tempo / 60.0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(self, voiced_chords: list[VoicedChord], output_path: str) -> None:
        """
        Render voiced chords to a Standard MIDI File (SMF format 1, 2 tracks).

        Args:
            voiced_chords: Ordered list of VoicedChord objects to write.
            output_path:   Destination file path (e.g. "output.mid").

        Raises:
            OSError: If the output file cannot be opened for writing.
        """
        midi = MIDIFile(numTracks=2, removeDuplicates=False, deinterleave=False)

        # --- Track 0: Left Hand ---
        midi.addTrackName(TRACK_LH, 0, "Left Hand (Bass)")
        midi.addTempo(TRACK_LH, 0, self.tempo)

        # --- Track 1: Right Hand ---
        midi.addTrackName(TRACK_RH, 0, "Right Hand (Chords)")
        midi.addTempo(TRACK_RH, 0, self.tempo)

        for vc in voiced_chords:
            start_beat = self._seconds_to_beats(vc.event.start_time)
            duration_beats = self._seconds_to_beats(vc.event.duration)

            # Left-hand bass notes → Track 0
            for pitch in vc.left_hand_notes:
                midi.addNote(
                    track=TRACK_LH,
                    channel=CHANNEL_LH,
                    pitch=pitch,
                    time=start_beat,
                    duration=duration_beats,
                    volume=self.BASS_VELOCITY,
                )

            # Right-hand triad notes → Track 1
            for pitch in vc.right_hand_notes:
                midi.addNote(
                    track=TRACK_RH,
                    channel=CHANNEL_RH,
                    pitch=pitch,
                    time=start_beat,
                    duration=duration_beats,
                    volume=self.velocity,
                )

        with open(output_path, "wb") as f:
            midi.writeFile(f)
