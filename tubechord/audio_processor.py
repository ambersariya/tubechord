"""AudioProcessor: Downloads audio from YouTube and extracts chroma features via librosa."""

import os
import shutil
import tempfile

import librosa
import numpy as np
import yt_dlp


class AudioProcessor:
    """
    Downloads audio from YouTube using yt-dlp and extracts chroma STFT features
    using librosa for Music Information Retrieval (MIR) analysis.

    Usage as a context manager ensures all temporary files are cleaned up:

        with AudioProcessor() as processor:
            chroma, hop_duration = processor.process(url)
    """

    def __init__(self, hop_length: int = 512, n_fft: int = 2048) -> None:
        self.hop_length = hop_length
        self.n_fft = n_fft
        self._temp_dirs: list[str] = []

    def get_video_title(self, url: str) -> str:
        """
        Fetch the video title from YouTube without downloading any media.

        Args:
            url: A valid YouTube video URL.

        Returns:
            The video title string, or "output" if the title cannot be determined.
        """
        ydl_opts = {"quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if isinstance(info, dict):
                return str(info.get("title", "output"))
            return "output"

    def download_audio(self, url: str) -> str:
        """
        Download audio from a YouTube URL and convert it to a WAV file.

        Args:
            url: A valid YouTube video URL.

        Returns:
            Absolute path to the downloaded WAV file.

        Raises:
            FileNotFoundError: If the download succeeded but the WAV file is missing.
            yt_dlp.utils.DownloadError: If yt-dlp cannot retrieve the video.
        """
        temp_dir = tempfile.mkdtemp(prefix="tubechord_")
        self._temp_dirs.append(temp_dir)

        output_stem = os.path.join(temp_dir, "audio")
        wav_path = output_stem + ".wav"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_stem + ".%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                }
            ],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(wav_path):
            raise FileNotFoundError(
                f"Expected WAV file not found at '{wav_path}'. "
                "Ensure ffmpeg is installed and accessible in your PATH."
            )

        return wav_path

    def extract_chroma(self, audio_path: str) -> tuple[np.ndarray, float, float]:
        """
        Load an audio file and compute its chroma STFT representation.

        Chroma STFT maps audio energy into 12 pitch classes (C, C#, D, ... B),
        collapsing octave information. This is the raw material for chord detection.

        Args:
            audio_path: Path to a WAV (or any librosa-compatible) audio file.

        Returns:
            A 3-tuple:
              - chroma (np.ndarray): shape (12, n_frames), values in [0, 1].
              - sample_rate (float): audio sample rate in Hz.
              - hop_duration (float): duration of each frame in seconds.
        """
        y, sr = librosa.load(audio_path, mono=True)
        chroma = librosa.feature.chroma_stft(
            y=y,
            sr=sr,
            hop_length=self.hop_length,
            n_fft=self.n_fft,
        )
        hop_duration = self.hop_length / sr
        return chroma, float(sr), hop_duration

    def process(self, url: str) -> tuple[np.ndarray, float]:
        """
        Full pipeline: download audio from YouTube and return its chromagram.

        Args:
            url: A valid YouTube video URL.

        Returns:
            A 2-tuple:
              - chroma (np.ndarray): shape (12, n_frames).
              - hop_duration (float): seconds per chroma frame.
        """
        audio_path = self.download_audio(url)
        chroma, _sr, hop_duration = self.extract_chroma(audio_path)
        return chroma, hop_duration

    def cleanup(self) -> None:
        """Remove all temporary directories created during processing."""
        for temp_dir in self._temp_dirs:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except OSError:
                pass
        self._temp_dirs.clear()

    def __enter__(self) -> "AudioProcessor":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.cleanup()
