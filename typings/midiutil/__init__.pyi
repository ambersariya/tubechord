from typing import BinaryIO

class MIDIFile:
    def __init__(
        self,
        numTracks: int = ...,
        removeDuplicates: bool = ...,
        deinterleave: bool = ...,
    ) -> None: ...

    def addTempo(self, track: int, time: float, tempo: float) -> None: ...
    def addTrackName(self, track: int, time: float, trackName: str) -> None: ...
    def addNote(
        self,
        track: int,
        channel: int,
        pitch: int,
        time: float,
        duration: float,
        volume: int,
    ) -> None: ...
    def writeFile(self, fileHandle: BinaryIO) -> None: ...
