"""
Whisper.cpp STT wrapper.
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import os


def sanitize_whisper_output(text: str) -> str:
    """
    Whisper often hallucinates the same 2-5 words many times on noise/reverb/echo.
    That yields TTS that sounds stuck repeating one phrase. Keep a single copy.
    Also call from any code path that runs whisper-cli directly (e.g. test_ui).
    """
    words = text.split()
    if len(words) < 8:
        return text
    # Consecutive repeated n-grams (try longer phrases first)
    for n in range(5, 1, -1):
        for start in range(0, min(20, len(words) - n * 3)):
            phrase = tuple(words[start : start + n])
            run = 0
            pos = start
            while pos + n <= len(words) and tuple(words[pos : pos + n]) == phrase:
                run += 1
                pos += n
            if run >= 3:
                return " ".join(words[: start + n]).strip()
    # Single-word stutter: "foo foo foo foo ..."
    for i in range(len(words) - 5):
        w = words[i]
        if all(words[i + j] == w for j in range(6)):
            return " ".join(words[: i + 1]).strip()
    return text


class WhisperSTT:
    """Whisper.cpp speech-to-text engine."""
    
    def __init__(
        self,
        whisper_path: str = "/usr/local/bin/whisper-cpp",
        model_path: str = "/home/jansky/jansky/whisper.cpp/models/ggml-base.en-q5_0.bin",
        language: str = "en",
        threads: int = 4
    ):
        self.whisper_path = whisper_path
        self.model_path = model_path
        self.language = language
        self.threads = threads
        
        # Verify paths
        if not Path(whisper_path).exists():
            # Try alternative paths
            alt_paths = [
                "/home/jansky/jansky/whisper.cpp/build/bin/whisper-cli",
                "/home/jansky/jansky/whisper.cpp/main",
            ]
            for alt in alt_paths:
                if Path(alt).exists():
                    self.whisper_path = alt
                    break
            else:
                raise FileNotFoundError(f"Whisper not found at {whisper_path}")
        
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found at {model_path}")
    
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text.
        
        Args:
            audio_path: Path to WAV file (16kHz, mono, 16-bit)
        
        Returns:
            Transcribed text
        """
        # Run whisper.cpp
        process = subprocess.run(
            [
                self.whisper_path,
                "-m", self.model_path,
                "-l", self.language,
                "-t", str(self.threads),
                "-np",  # No prints except results
                "-ng",  # Disable GPU - fixes Metal memory crash on Mac
                "-nt",  # No timestamps — otherwise stdout is "[hh:mm ...] text" and breaks parsing
                audio_path  # File as positional argument at the end
            ],
            capture_output=True,
            text=True,
            timeout=60  # CPU mode is slower
        )
        
        if process.returncode != 0:
            raise RuntimeError(f"Whisper failed: {process.stderr}")
        
        text = process.stdout.strip()
        text = text.replace("[BLANK_AUDIO]", "").strip()
        text = sanitize_whisper_output(text)

        return text
    
    def transcribe_audio_array(self, audio, sample_rate: int = 16000) -> str:
        """
        Transcribe audio from numpy array.
        
        Args:
            audio: Numpy array of audio samples
            sample_rate: Sample rate of audio
        
        Returns:
            Transcribed text
        """
        import numpy as np
        import wave
        
        # Save to temp file
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            with wave.open(temp_path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio.tobytes())
            
            return self.transcribe(temp_path)
        finally:
            os.unlink(temp_path)
